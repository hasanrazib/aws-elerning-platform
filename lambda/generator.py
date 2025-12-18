def handler(event, context):
    print("GENERATOR EVENT:", event)
    return {"ok": True}
