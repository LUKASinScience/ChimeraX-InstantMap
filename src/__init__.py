from chimerax.core.toolshed import BundleAPI


class _InstantMapAPI(BundleAPI):

    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        if ti.name == "inSTAnt Map":
            from .tool import InstantMapTool
            return InstantMapTool(session, ti.name)

    @staticmethod
    def get_class(class_name):
        if class_name == "InstantMapTool":
            from .tool import InstantMapTool
            return InstantMapTool


bundle_api = _InstantMapAPI()