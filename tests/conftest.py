import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    testfunction = pyfuncitem.obj
    if inspect.iscoroutinefunction(testfunction):
        argnames = pyfuncitem._fixtureinfo.argnames
        kwargs = {arg: pyfuncitem.funcargs[arg] for arg in argnames if arg in pyfuncitem.funcargs}
        asyncio.run(testfunction(**kwargs))
        return True
    return None
