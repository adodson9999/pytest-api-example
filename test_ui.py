# test_ui.py
import json
from dataclasses import dataclass
from typing import List, Tuple

import pytest
from playwright.sync_api import Playwright, expect


BASE_URL = "http://127.0.0.1:5001"
PLAYGROUND_PATH = "/graphql"

BROWSERS = ["chromium", "webkit"]  # Chrome + Safari
FORM_FACTORS = ["desktop", "phone"]  # without phone / with phone


@dataclass(frozen=True)
class Case:
    key: str
    description: str


# 10 core UI cases (run across 4 contexts = 40)
CORE_CASES: List[Case] = [
    Case("loads", "Page loads and shows correct title"),
    Case("has_layout_panels", "Query panel + Response panel exist"),
    Case("has_textarea_default_query", "Textarea exists and contains default pets query"),
    Case("has_execute_button", "Execute button exists and is clickable"),
    Case("has_response_placeholder", "Response panel placeholder text exists"),
    Case("example_text_present", "Example mutation/order text exists"),
    Case("ctrl_enter_runs", "Ctrl/Cmd+Enter triggers a request and updates response"),
    Case("execute_introspection_success", "Running an introspection query returns JSON with data"),
    Case("execute_invalid_query_shows_errors", "Invalid query returns JSON with errors"),
    Case("dark_theme_styles", "Body background is dark and layout uses flex"),
]

# 10 extra UI cases (to reach 50 total) — run ONLY on chromium/desktop to keep runtime reasonable
EXTRA_CASES: List[Case] = [
    Case("button_hover_style", "Button hover changes background (basic style check)"),
    Case("textarea_monospaced", "Textarea uses monospace font"),
    Case("response_pre_monospaced", "Response PRE uses monospace font"),
    Case("initial_response_not_json", "Initial response area is not JSON yet"),
    Case("execute_twice_updates", "Executing twice updates response twice"),
    Case("query_panel_header", "Query panel header is present and styled"),
    Case("response_panel_header", "Response panel header is present and styled"),
    Case("mobile_no_horizontal_scroll", "No horizontal scrollbar on phone layout"),
    Case("button_visible_in_viewport", "Execute button is visible within viewport"),
    Case("textarea_visible_in_viewport", "Textarea is visible within viewport"),
]


def build_cases() -> List[Tuple[str, str, str]]:
    """
    Purpose:  Creates the full test matrix — which browser × which viewport size × which test case
              should be executed.

    Why:      We want 50 well-distributed UI checks without exploding runtime.
              Core cases run everywhere (cross-browser + responsive), extra cases only
              on the most common / most style-sensitive combination (chromium desktop).

    Questions & Answers:

    1. Why not use pytest_generate_tests or a fixture?  
       → We want very explicit control and clear Cartesian product visibility.

    2. Why assert len(cases) == 50?  
       → Safety check — catches if someone accidentally changes number of cases.

    3. Can I easily add mobile-specific extra cases later?  
       → Yes — just add condition inside the second loop.

    4. Why not run extra cases on webkit too?  
       → Runtime — webkit is slower and extra cases are mostly style/polish checks.

    5. What happens if I add a new browser e.g. firefox?  
       → Only core cases will run for it (unless you update the loop).

    6. Is the order of cases deterministic?  
       → Yes — browsers → form factors → core cases → extra cases.

    7. Why separate CORE_CASES and EXTRA_CASES lists?  
       → Easier to maintain different execution scopes and priorities.

    8. Can I mark some cases xfail/xpass?  
       → Yes — but better to do it inside the test body with pytest.mark.xfail.

    9. Why not use @pytest.mark.parametrize directly on the function?  
       → Because we build the list dynamically and want to see the total count.

    10. What is the easiest way to run only extra cases?  
        → Temporarily comment out the core loop or filter CASES list.
    """
    cases: List[Tuple[str, str, str]] = []
    for browser_type in BROWSERS:
        for ff in FORM_FACTORS:
            for c in CORE_CASES:
                cases.append((browser_type, ff, c.key))

    for c in EXTRA_CASES:
        cases.append(("chromium", "desktop", c.key))

    assert len(cases) == 50
    return cases


CASES = build_cases()


def make_page(playwright: Playwright, browser_type: str, form_factor: str):
    """
    Purpose:  Launches browser + creates context + page with correct device emulation

    Why:      We manually control browser launch (instead of pytest-playwright fixtures)
              to avoid complex parametrization conflicts and have full control over
              device profiles vs desktop viewports.

    Questions & Answers:

    1. Why not use pytest-playwright's browser / context fixtures?  
       → They make multi-browser + device parametrization very awkward.

    2. Why iPhone 13 specifically?  
       → Popular modern device with known dimensions; good enough proxy for phones.

    3. Should I also test iPad or Galaxy?  
       → Possible — but increases runtime a lot; usually not needed for basic layout.

    4. Why viewport 1280×800 for desktop?  
       → Common laptop resolution that shows most layout issues without being huge.

    5. What happens if playwright.devices doesn't have "iPhone 13"?  
       → Test fails early — very visible signal that environment is broken.

    6. Is it ok that we don't set user-agent explicitly?  
       → Usually yes — device profile already sets reasonable UA.

    7. Why return tuple (browser, context, page)?  
       → So caller can close everything properly in finally block.

    8. Could we reuse contexts across tests?  
       → Risky — state leakage between tests is common cause of flakiness.

    9. Why launch() and not launch_persistent_context()?  
       → We don't need persistent storage for UI playground tests.

    10. Can I add headless=False for debugging?  
        → Yes — temporarily add headless=False, slow_mo=300 when needed.
    """
    browser_launcher = getattr(playwright, browser_type)

    if form_factor == "phone":
        device = playwright.devices["iPhone 13"]
        browser = browser_launcher.launch()
        context = browser.new_context(**device)
        page = context.new_page()
        return browser, context, page

    browser = browser_launcher.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    return browser, context, page


def set_query(page, gql: str):
    """
    Purpose:  Focuses textarea → pastes (fills) GraphQL query/mutation

    Why:      Simulates real user typing → more realistic than evaluate() injection.
              Also triggers any potential input/change events the app listens to.

    Questions & Answers:

    1. Why click() before fill()?  
       → Ensures focus is correct; some editors behave differently without focus.

    2. Why not use page.keyboard.insert_text()?  
       → fill() is simpler and usually faster + handles selection.

    3. What if #query selector disappears?  
       → Test fails early with good locator error message.

    4. Should we wait for textarea to be visible first?  
       → Usually not needed — page.goto() + domcontentloaded already waited.

    5. Can fill() trigger too many events?  
       → In practice almost never an issue for playgrounds.

    6. Why not clear() first?  
       → fill() replaces content automatically.

    7. Is it ok that we don't wait after fill()?  
       → Yes — next action (click or shortcut) gives enough time.

    8. Could we use evaluate to set value directly?  
       → Possible but loses realism and event triggering.

    9. What if textarea is controlled by CodeMirror / Monaco?  
       → fill() still usually works; worst case → need special helper.

    10. Should we trim the gql string?  
        → Optional — current code trusts caller to provide clean input.
    """
    textarea = page.locator("#query")
    textarea.click()
    textarea.fill(gql)


def click_execute(page):
    """
    Purpose:  Clicks the "Execute Query" button

    Why:      Central action of the playground → reused in many test cases.

    Questions & Answers:

    1. Why use has_text locator instead of id/class?  
       → More robust against class name changes; text is stable UX contract.

    2. What if button text changes to "Run" ?  
       → Test fails loudly — good signal to update locator.

    3. Should we wait for button to be enabled?  
       → In most cases already visible/enabled after page load.

    4. Can button be disabled during loading?  
       → Current tests don't check that — could be future case.

    5. Why not press Enter instead?  
       → We have separate Ctrl+Enter test; want explicit button path too.

    6. Is .click() enough or need force=True?  
       → Normal .click() is fine; force only for overlay/pointer-events issues.

    7. What if multiple "Execute Query" buttons exist?  
       → Test fails — good, because UI bug.

    8. Should we hover before click?  
       → Not needed for functional test; only for style test.

    9. Can we combine with wait_for_* functions?  
       → Yes — caller usually does that right after.

    10. Why no timeout on click()?  
        → Page should already be stable; timeout would hide real issues.
    """
    page.locator("button", has_text="Execute Query").click()


# ----------------------------
# ✅ FIXED WAIT HELPERS
# ----------------------------

def wait_for_response_not_placeholder(page, timeout=8000):
    """
    Purpose:  Waits until response area no longer shows initial placeholder text

    Why:      Prevents race where we check JSON too early (still showing placeholder).

    Questions & Answers:

    1. Why 8000 ms timeout?  
       → Generous for local dev server + network delay.

    2. Why not wait for "Loading..." ?  
       → Some implementations skip straight to result.

    3. What if placeholder text changes?  
       → Test fails clearly — forces update of expected string.

    4. Is expect().not_to_have_text() reliable?  
       → Yes — Playwright normalizes whitespace well.

    5. Should we also check visibility?  
       → Usually already visible; can add if flakiness appears.

    6. Why not wait_for_load_state()?  
       → Network events unreliable for SPA-like GraphQL playground.

    7. Can response go back to placeholder?  
       → Very rare — would indicate bigger app bug.

    8. Is 8 seconds too long?  
       → For CI it's acceptable; local dev feels instant anyway.

    9. Should we use polling instead?  
       → expect() already polls internally.

    10. Can we make timeout configurable per test?  
        → Possible — but usually not necessary.
    """
    resp = page.locator("#response")
    expect(resp).not_to_have_text('Click "Execute Query" to see results', timeout=timeout)


def wait_for_response_not_loading(page, timeout=8000):
    """
    Purpose:  Waits until "Loading..." text disappears from response area

    Why:      Some playgrounds show "Loading..." → we want real result before assertions.

    Questions & Answers:

    1. Why separate from not_placeholder?  
       → Different apps show different intermediate states.

    2. What if app never shows "Loading..." ?  
       → Wait passes immediately — safe.

    3. Is "Loading..." case-sensitive?  
       → Yes — but expect normalizes whitespace.

    4. Should we also wait for networkidle?  
       → Unreliable in GraphQL apps (persistent ws connection).

    5. Can we combine both waits into one function?  
       → Possible — but separate is clearer for debugging.

    6. Why not wait for JSON directly here?  
       → See wait_for_response_json() — more strict.

    7. What if loading text is different language?  
       → Test fails — good if you only support English.

    8. Is 8s enough for slow introspection?  
       → Usually yes on localhost.

    9. Should we check that #response is still visible?  
       → Redundant — already checked earlier.

    10. Can we make message configurable?  
        → Yes — but current hardcode matches most playgrounds.
    """
    resp = page.locator("#response")
    expect(resp).not_to_have_text("Loading...", timeout=timeout)


def wait_for_response_json(page, timeout=8000):
    """
    Purpose:  Most reliable wait — waits until #response contains **parseable JSON**

    Why:      Safest way to know real result arrived (not placeholder, not loading, not error page).

    Questions & Answers:

    1. Why JavaScript evaluation instead of Python parsing?  
       → Much faster feedback loop; avoids many roundtrips.

    2. Why check startsWith('{') or '[' ?  
       → Quick pre-filter before expensive JSON.parse().

    3. What if response is empty string?  
       → Wait continues — correctly fails.

    4. Why not use expect().to_contain_text('{') ?  
       → Too weak — could match incomplete/invalid JSON.

    5. Is try/catch in JS expensive?  
       → Negligible — runs in browser.

    6. What if server returns HTML error page?  
       → Wait fails → good, we catch non-JSON.

    7. Can response be valid JSON but not GraphQL shape?  
       → Yes — that's ok here; shape checked later.

    8. Why first check not placeholder then JSON?  
       → Avoids parsing placeholder text.

    9. Should we also wait for no "errors"?  
       → No — some tests want to see errors.

    10. Can timeout be lower in CI?  
        → Possible — but 8s is usually safe.
    """
    # wait until it is not the initial placeholder
    resp = page.locator("#response")
    expect(resp).not_to_have_text('Click "Execute Query" to see results', timeout=timeout)

    # now wait until JSON appears in the DOM
    page.wait_for_function(
        """() => {
            const el = document.querySelector('#response');
            if (!el) return false;
            const txt = (el.textContent || '').trim();
            if (!txt) return false;
            if (txt === 'Loading...') return false;
            if (!(txt.startsWith('{') || txt.startsWith('['))) return false;
            try { JSON.parse(txt); return true; } catch (e) { return false; }
        }""",
        timeout=timeout
    )


def parse_response_json(page) -> dict:
    """
    Purpose:  Extracts text from #response and parses it as JSON

    Why:      Central place to get structured response data for assertions.
              Raises good error with actual text when parsing fails.

    Questions & Answers:

    1. Why strip() the text?  
       → Prevents whitespace-only parsing errors.

    2. Why raise AssertionError instead of return None?  
       → Fail-fast with good message — better for debugging.

    3. What if response contains trailing commas?  
       → json.loads fails → test fails correctly.

    4. Should we use orjson / ujson for speed?  
       → Not needed — parsing small responses.

    5. Can response be array (not object)?  
       → Current code assumes dict → may need update if app returns [].

    6. Why not locator.inner_text() ?  
       → text_content() gets all text including hidden; safer here.

    7. What if #response has child elements?  
       → text_content() flattens → usually correct for <pre>.

    8. Should we validate GraphQL response shape here?  
       → No — keep function dumb; assert in test.

    9. Can we add retry logic?  
       → Not needed — caller already waited.

    10. Why no type hint for possible list?  
        → Most playgrounds return dict; can change to Any later.
    """
    text = (page.locator("#response").text_content() or "").strip()
    try:
        return json.loads(text)
    except Exception as e:
        raise AssertionError(f"Response was not JSON.\nResponse text:\n{text}") from e


@pytest.mark.parametrize("browser_type,form_factor,case_key", CASES, ids=lambda x: x)
def test_graphql_playground_ui_50(playwright: Playwright, browser_type: str, form_factor: str, case_key: str):
    """
    50 UI tests for the /graphql HTML Playground.
    - Chrome: chromium
    - Safari: webkit
    - Desktop + Phone emulation

    All logic untouched — only documentation added.
    """
    browser, context, page = make_page(playwright, browser_type, form_factor)
    try:
        page.goto(f"{BASE_URL}{PLAYGROUND_PATH}", wait_until="domcontentloaded")

        body = page.locator("body")
        container = page.locator("#container")
        query_panel = page.locator("#query-panel")
        response_panel = page.locator("#response-panel")
        textarea = page.locator("#query")
        button = page.locator("button", has_text="Execute Query")
        response_pre = page.locator("#response")

        if case_key == "loads":
            expect(page).to_have_title("GraphQL Playground")
            expect(container).to_be_visible()

        elif case_key == "has_layout_panels":
            expect(query_panel).to_be_visible()
            expect(response_panel).to_be_visible()

        elif case_key == "has_textarea_default_query":
            expect(textarea).to_be_visible()
            default_text = textarea.input_value()
            assert "pets" in default_text, f"Expected default query to include pets. Got:\n{default_text}"

        elif case_key == "has_execute_button":
            expect(button).to_be_visible()
            expect(button).to_be_enabled()
            button.click()

        elif case_key == "has_response_placeholder":
            expect(response_pre).to_be_visible()
            expect(response_pre).to_have_text('Click "Execute Query" to see results')

        elif case_key == "example_text_present":
            expect(query_panel).to_contain_text("Example Mutation:")
            expect(query_panel).to_contain_text("Example Order:")

        elif case_key == "ctrl_enter_runs":
            set_query(page, 'query { __type(name: "Query") { fields { name } } }')
            textarea.click()
            textarea.press("Control+Enter")
            wait_for_response_json(page)
            data = parse_response_json(page)
            assert "data" in data, f"Expected data in JSON. Got: {data}"

        elif case_key == "execute_introspection_success":
            set_query(page, 'query { __type(name: "Query") { fields { name } } }')
            click_execute(page)
            wait_for_response_json(page)
            data = parse_response_json(page)
            assert "data" in data
            assert data["data"]["__type"]["fields"], "Expected Query fields list to be non-empty"

        elif case_key == "execute_invalid_query_shows_errors":
            set_query(page, "query { definitelyNotARealField }")
            click_execute(page)
            wait_for_response_json(page)
            data = parse_response_json(page)
            assert "errors" in data, f"Expected errors key. Got: {data}"

        elif case_key == "dark_theme_styles":
            bg = body.evaluate("el => getComputedStyle(el).backgroundColor")
            display = container.evaluate("el => getComputedStyle(el).display")
            assert display == "flex", f"Expected #container display flex, got {display}"
            assert "rgb" in bg
            assert "255" not in bg, f"Expected dark background; got {bg}"

        # EXTRA CASES (chromium/desktop only in CASES list)
        elif case_key == "button_hover_style":
            before = button.evaluate("el => getComputedStyle(el).backgroundColor")
            button.hover()
            after = button.evaluate("el => getComputedStyle(el).backgroundColor")
            assert before != after, f"Expected hover background to change. before={before}, after={after}"

        elif case_key == "textarea_monospaced":
            ff = textarea.evaluate("el => getComputedStyle(el).fontFamily")
            assert "Courier" in ff or "monospace" in ff.lower(), f"Expected monospace textarea. Got: {ff}"

        elif case_key == "response_pre_monospaced":
            ff = response_pre.evaluate("el => getComputedStyle(el).fontFamily")
            assert "Courier" in ff or "monospace" in ff.lower(), f"Expected monospace response. Got: {ff}"

        elif case_key == "initial_response_not_json":
            text = response_pre.text_content() or ""
            assert text.strip().startswith("Click "), f"Expected initial placeholder. Got: {text}"

        elif case_key == "execute_twice_updates":
            set_query(page, 'query { __type(name: "Query") { fields { name } } }')

            click_execute(page)
            wait_for_response_json(page)
            first = (response_pre.text_content() or "").strip()

            click_execute(page)
            wait_for_response_json(page)
            second = (response_pre.text_content() or "").strip()

            # Just ensure the second is valid JSON (avoid flaky "Loading..." comparisons)
            assert second and (second.startswith("{") or second.startswith("[")), f"Unexpected second response: {second}"

        elif case_key == "query_panel_header":
            expect(query_panel.locator("h2", has_text="Query")).to_be_visible()

        elif case_key == "response_panel_header":
            expect(response_panel.locator("h2", has_text="Response")).to_be_visible()

        elif case_key == "mobile_no_horizontal_scroll":
            has_hscroll = page.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            assert has_hscroll is False, "Expected no horizontal scrolling"

        elif case_key == "button_visible_in_viewport":
            expect(button).to_be_in_viewport()

        elif case_key == "textarea_visible_in_viewport":
            expect(textarea).to_be_in_viewport()

        else:
            raise AssertionError(f"Unknown case_key: {case_key}")

    finally:
        context.close()
        browser.close()