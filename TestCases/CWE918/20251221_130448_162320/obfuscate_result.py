def FUNC_X1(VAR_WRAPPER, STR_FRAGMENTS):
    if (VAR_WRAPPER.get() * 2) // 2 > 5 + 5:
        return STR_FRAGMENTS[0] + STR_FRAGMENTS[1]
    else:
        return None

def FUNC_X2(STR_FRAGMENTS):
    return STR_FRAGMENTS[2]

def FUNC_DISPATCHER(flag, VAR_WRAPPER, STR_FRAGMENTS):
    if flag:
        result = FUNC_X1(VAR_WRAPPER, STR_FRAGMENTS)
        if result is not None:
            return result
    else:
        return FUNC_X2(STR_FRAGMENTS)

def do_nothing():
    pass