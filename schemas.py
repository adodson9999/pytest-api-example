pet = {
    "type": "object",
    "required": ["name", "type"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string"
        },
        "type": {
            "type": "string",
            "enum": ["dog", "cat", "bird", "rabbit"]
        },
        "status": {
            "type": "string",
            "enum": ["available", "sold", "pending"]
        }
    }
}



customer = {
    "type": "object",
    "required": ["name", "date", "purchase"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string"
        },
        "date": {
            "type": "string",
        },
        "purchase": {
            "type": "integer",
        },
        "email": {
            "type": "string",
        },
    }
}


inventory = {
    "type": "object",
    "required": ["id", "inventory"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "inventory": {
            "type": "integer"
        }
    }
}

vet = {
    "type": "object",
    "required": ["name", "contact_form", "contact_info"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string"
        },
        "contact_form": {
            "type": "string",
            "enum": ["phone", "email", "website"]
        },
        "contact_info": {
            "type": "integer",
        },
    }
}


event = {
    "type": "object",
    "required": ["name", "date", "location"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string",
        },
        "date": {
            "type": "string",
        },
        "location": {
            "type": "integer",
        },
    }
    
}

trainer = {
    "type": "object",
    "required": ["name", "contact_form", 'contact_info'],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string",
        },
        "contact_form": {
            "type": "string",
            "enum": ["phone", "email", "website", "text"]
        },
        "contact_info": {
            "type": "integer",
        },
    }
}

vendor = {
    "type": "object",
    "required": ["name", "point_of_contact", "product"],
    "properties": {
        "id": {
            "type": "integer"
        },
        "name": {
            "type": "string",
        },
        "contact_form": {
            "type": "string",
            "enum": ["phone", "email", "website"]
        },
        "contact": {
            "type": "string",
        },
        "point_of_contact": {
            "type": "string",
        },
        "product": {
            "type": "integer",
        },
    }
}