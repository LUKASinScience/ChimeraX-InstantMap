"""`instantmap mask #map threshold T [extend E] [softEdge W] [lowpass A] [output file.mrc]`: a RELION-style soft mask from a map.

The new mask sits on exactly the grid of the source map (origin, voxel size, cell angles, rotation, placement), so it can
be used as a RELION external mask for that map. The maths is in mask_core.py."""
import numpy as np

from chimerax.core.commands import CmdDesc, FloatArg, SaveFileNameArg, run, quote_path_if_necessary
from chimerax.core.errors import UserError
from chimerax.map import MapArg

from .mask_core import make_mask


def instantmap_mask(session, volume, threshold=None, extend=0.0, soft_edge=0.0, lowpass=None, output=None):
    data = volume.data
    if threshold is None:
        surfaces = getattr(volume, "surfaces", None)
        if not surfaces:
            raise UserError("give 'threshold' (the map has no displayed surface level to start from)")
        threshold = surfaces[0].level
    matrix = np.asarray(volume.full_matrix())
    try:
        mask = make_mask(matrix, threshold, extend=extend, soft_edge=soft_edge, lowpass=lowpass, angpix=float(data.step[0]))
    except (ValueError, RuntimeError) as exc:
        raise UserError(str(exc))
    from chimerax.map_data import ArrayGridData
    from chimerax.map import volume_from_grid_data
    grid = ArrayGridData(mask, origin=tuple(data.origin), step=tuple(data.step),
                         cell_angles=tuple(getattr(data, "cell_angles", (90, 90, 90))),
                         rotation=getattr(data, "rotation", ((1, 0, 0), (0, 1, 0), (0, 0, 1))),
                         name="%s mask" % volume.name)
    new = volume_from_grid_data(grid, session, style="image", open_model=True, show_dialog=False)
    new.position = volume.position
    session.logger.info("instantmap mask: %s -> #%s (threshold %g, extend %g voxels, soft edge %g voxels%s); %d voxels at 1, %d in between"
                        % (volume.name, new.id_string, threshold, extend, soft_edge,
                           ", low-pass %g A" % lowpass if lowpass else "", int((mask == 1).sum()), int(((mask > 0) & (mask < 1)).sum())))
    if output:
        run(session, "save %s models #%s" % (quote_path_if_necessary(output), new.id_string))
        session.logger.info("instantmap mask: saved %s" % output)
    return new


instantmap_mask_desc = CmdDesc(
    required=[("volume", MapArg)],
    keyword=[("threshold", FloatArg), ("extend", FloatArg), ("soft_edge", FloatArg), ("lowpass", FloatArg), ("output", SaveFileNameArg)],
    synopsis="Make a RELION-style soft mask from a map (low-pass, threshold, extend, soft edge); same grid as the map",
)
