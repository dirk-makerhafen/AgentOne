def filter_zero(msg: str = "", num: int = 0) -> dict | None:
    if "0" in str(msg):
        return None
    return {"msg": msg, "num": num}
