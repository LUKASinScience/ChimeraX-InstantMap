"""One-line tip about reliontree, shown in the log at startup until dismissed."""
from chimerax.core.settings import Settings

URL = "https://lukasinscience.github.io/reliontree/"      # the reliontree guide


class _Prefs(Settings):
    AUTO_SAVE = {"hint_hidden": False}


def _prefs(session):
    return _Prefs(session, "InstantMap")


def show(session):
    if _prefs(session).hint_hidden:
        return
    session.logger.info(
        'InstantMap tip: <a href="%s">reliontree</a> shows your whole RELION job tree in the browser '
        '(parameter diffs, class maps, "why this job?"). Run <b>instantmap listen</b> here and its '
        '<b>3D</b> buttons open maps in this window. '
        '<a href="cxcmd:instantmap hint false">Don\'t show again</a>' % URL,
        is_html=True)


def set_shown(session, shown=True):
    _prefs(session).hint_hidden = not shown
    session.logger.info("InstantMap tip %s." % ("will be shown at startup" if shown else "hidden"))
