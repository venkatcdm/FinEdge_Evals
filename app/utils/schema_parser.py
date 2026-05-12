def extract_fields(schema, parent=""):

    fields = []

    properties = schema.get("properties", {})

    for key, value in properties.items():

        full_key = (
            f"{parent}.{key}"
            if parent
            else key
        )

        field_type = value.get("type")

        # Primitive field
        if field_type in [
            "string",
            "number",
            "integer",
            "boolean"
        ]:
            fields.append(full_key)

        # Nested object
        elif field_type == "object":

            nested = extract_fields(
                value,
                full_key
            )

            fields.extend(nested)

        # Array
        elif field_type == "array":

            items = value.get("items", {})

            if items.get("type") == "object":

                nested = extract_fields(
                    items,
                    full_key
                )

                fields.extend(nested)

            else:
                fields.append(full_key)

    return fields