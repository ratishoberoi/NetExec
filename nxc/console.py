from rich.console import Console

def make_console(file):
    return Console(file=file, soft_wrap=True, tab_size=4)

nxc_console = make_console(None)
