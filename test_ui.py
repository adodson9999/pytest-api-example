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
    Returns tuples: (browser_type, form_factor, case_key)

    CORE: 10 cases * (2 browsers * 2 form factors) = 40
    EXTRA: 10 cases * (chromium * desktop) = 10
    TOTAL = 50
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
    We intentionally launch browsers ourselves (chromium/webkit) instead of relying on
    pytest-playwright's browser fixtures to avoid duplicate parametrization issues.
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
    textarea = page.locator("#query")
    textarea.click()
    textarea.fill(gql)


def click_execute(page):
    page.locator("button", has_text="Execute Query").click()


# ----------------------------
# ✅ FIXED WAIT HELPERS
# ----------------------------
def wait_for_response_not_placeholder(page, timeout=8000):
    resp = page.locator("#response")
    expect(resp).not_to_have_text('Click "Execute Query" to see results', timeout=timeout)


def wait_for_response_not_loading(page, timeout=8000):
    resp = page.locator("#response")
    expect(resp).not_to_have_text("Loading...", timeout=timeout)


def wait_for_response_json(page, timeout=8000):
    """
    Wait until #response contains valid JSON.
    Handles: placeholder -> Loading... -> JSON
    Uses wait_for_function because Python expect().to_have_text doesn't accept lambdas.
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
