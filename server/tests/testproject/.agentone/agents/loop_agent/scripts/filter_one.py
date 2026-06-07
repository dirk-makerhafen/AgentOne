def filter_one(msg: str = "", num: int = 0) -> dict | None:
    if "1" in str(msg):
        return None
    return {"msg": msg, "num": num}
