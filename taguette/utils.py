def _f(message):
    """Pass-through translation function.

    Marks a string for translation without translating it at run time.
    """
    return message


class DefaultMap(object):
    def __init__(self, default, mapping):
        self.__default = default
        self.mapping = mapping

    def get(self, key):
        try:
            return self.mapping[key]
        except KeyError:
            return self.__default(key)

    def __getitem__(self, key):
        return self.get(key)


async def log_and_wait_proc(logger, proc):
    while proc.returncode is None:
        line = await proc.stdout.readline()
        if not line:
            break
        line = line.decode('utf-8', 'replace')
        if line[-1] == '\n':
            line = line[:-1]
        logger.info("%d: %s", proc.pid, line)

    ret = await proc.wait()
    line = await proc.stdout.read()
    if line:
        line = line.decode('utf-8', 'replace')
        if line[-1] == '\n':
            line = line[:-1]
        logger.info("%d: %s", proc.pid, line)
    return ret
