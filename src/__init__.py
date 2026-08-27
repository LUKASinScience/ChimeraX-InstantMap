from chimerax.core.toolshed import BundleAPI


class _InstantMapAPI(BundleAPI):

    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        if ti.name == "InstantMap":
            from .tool import InstantMapTool
            return InstantMapTool(session, ti.name)

    @staticmethod
    def get_class(class_name):
        if class_name == "InstantMapTool":
            from .tool import InstantMapTool
            return InstantMapTool

    @staticmethod
    def run_provider(session, name, mgr, **kw):
        """Show the InstantMap tool when its EM-tab toolbar button is clicked."""
        from chimerax.core.commands import run
        run(session, 'ui tool show "InstantMap"')


bundle_api = _InstantMapAPI()