import adsk.core
import adsk.fusion
import traceback


# Provisional dimensions in millimetres. Change these after measuring the board.
GPS_LENGTH = 30.0
GPS_WIDTH = 22.0
GPS_MAX_HEIGHT = 8.0
SMA_HOLE_DIAMETER = 7.0

WALL = 2.4
FLOOR = 2.4
CLEARANCE = 0.6
CASE_INNER_LENGTH = 91.0
CASE_INNER_WIDTH = 62.0
CASE_INNER_HEIGHT = 29.0
LID_THICKNESS = 2.4


def cm(mm):
    return mm / 10.0


def value(mm):
    return adsk.core.ValueInput.createByString(f'{mm} mm')


def component(root, name, x_offset=0):
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(cm(x_offset), 0, 0)
    occurrence = root.occurrences.addNewComponent(matrix)
    occurrence.component.name = name
    return occurrence.component


def offset_plane(comp, z):
    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(comp.xYConstructionPlane, value(z))
    return planes.add(plane_input)


def rectangle_feature(comp, name, x, y, z, length, width, height,
                      operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation):
    plane = comp.xYConstructionPlane if z == 0 else offset_plane(comp, z)
    sketch = comp.sketches.add(plane)
    sketch.name = name
    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(cm(x), cm(y), 0),
        adsk.core.Point3D.create(cm(x + length), cm(y + width), 0)
    )
    profile = sketch.profiles.item(0)
    extrudes = comp.features.extrudeFeatures
    extrude_input = extrudes.createInput(profile, operation)
    extrude_input.setDistanceExtent(False, value(height))
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def rear_wall_hole(comp, name, center_x, center_z, wall_y, diameter):
    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    # Fusion's positive offset from the XZ plane points toward negative Y.
    plane_input.setByOffset(comp.xZConstructionPlane, value(-wall_y))
    plane = planes.add(plane_input)
    sketch = comp.sketches.add(plane)
    sketch.name = name
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(cm(center_x), cm(center_z), 0), cm(diameter / 2)
    )
    extrudes = comp.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
    extrude_input.setSymmetricExtent(value(WALL + 2.0), False)
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def body_shell(comp):
    outer_l = CASE_INNER_LENGTH + 2 * WALL
    outer_w = CASE_INNER_WIDTH + 2 * WALL
    outer_h = CASE_INNER_HEIGHT + FLOOR

    rectangle_feature(comp, 'Case outer body', 0, 0, 0, outer_l, outer_w, outer_h)
    rectangle_feature(
        comp, 'Case cavity', WALL, WALL, FLOOR,
        CASE_INNER_LENGTH, CASE_INNER_WIDTH, CASE_INNER_HEIGHT + 1,
        adsk.fusion.FeatureOperations.CutFeatureOperation
    )

    # Pi 4 mounting posts: standard 58 x 49 mm hole pattern, M2.5 clearance.
    pi_x = WALL + 3.5 + 2.5
    pi_y = WALL + 3.5 + 2.5
    for index, (x, y) in enumerate(((pi_x, pi_y), (pi_x + 58, pi_y),
                                    (pi_x, pi_y + 49), (pi_x + 58, pi_y + 49)), 1):
        sketch = comp.sketches.add(offset_plane(comp, FLOOR))
        sketch.name = f'Pi post {index}'
        circles = sketch.sketchCurves.sketchCircles
        circles.addByCenterRadius(adsk.core.Point3D.create(cm(x), cm(y), 0), cm(3.0))
        post = comp.features.extrudeFeatures.createInput(
            sketch.profiles.item(0), adsk.fusion.FeatureOperations.JoinFeatureOperation)
        post.setDistanceExtent(False, value(4.0))
        comp.features.extrudeFeatures.add(post)

        hole_sketch = comp.sketches.add(offset_plane(comp, FLOOR))
        hole_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cm(x), cm(y), 0), cm(1.35))
        hole = comp.features.extrudeFeatures.createInput(
            hole_sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        hole.setDistanceExtent(False, value(5.0))
        comp.features.extrudeFeatures.add(hole)

    # Separate top-open Pi 4 port cut-outs. Their upper edge is closed by the lid.
    top = outer_h - 17.0
    rectangle_feature(comp, 'Ethernet opening', outer_l - WALL - 1, 6.0, top,
                      WALL + 2, 17.5, 18.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'USB pair 1 opening', outer_l - WALL - 1, 25.0, top,
                      WALL + 2, 15.5, 18.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'USB pair 2 opening', outer_l - WALL - 1, 42.0, top,
                      WALL + 2, 15.5, 18.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

    rectangle_feature(comp, 'USB-C opening', 8.0, -1.0, top + 4.0,
                      11.0, WALL + 2, 14.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'Micro-HDMI 1 opening', 24.0, -1.0, top + 5.0,
                      9.0, WALL + 2, 13.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'Micro-HDMI 2 opening', 37.0, -1.0, top + 5.0,
                      9.0, WALL + 2, 13.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'Audio opening', 54.0, -1.0, top + 4.0,
                      10.0, WALL + 2, 14.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    rectangle_feature(comp, 'MicroSD opening', -1.0, 23.0, 4.0,
                      WALL + 2, 18.0, 8.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

    # The SMA hole shares the GPS cradle centreline, so both move together.
    gps_x = (outer_l - GPS_LENGTH) / 2
    sma_center_x = gps_x + GPS_LENGTH / 2
    rectangle_feature(
        comp, 'GPS SMA opening', sma_center_x - SMA_HOLE_DIAMETER / 2,
        outer_w - WALL - 1, outer_h - 12.0,
        SMA_HOLE_DIAMETER, WALL + 2, 13.0,
        adsk.fusion.FeatureOperations.CutFeatureOperation
    )


def lid(comp, x_offset=0):
    outer_l = CASE_INNER_LENGTH + 2 * WALL
    outer_w = CASE_INNER_WIDTH + 2 * WALL
    rectangle_feature(comp, 'Lid', x_offset, 0, 0, outer_l, outer_w, LID_THICKNESS)

    # Inner locating rim, discontinuous so it can flex when snapped into place.
    rim_h = 3.0
    rim_t = 1.2
    inset = WALL + CLEARANCE
    rectangle_feature(comp, 'Lid rim front', x_offset + inset + 8, inset, LID_THICKNESS,
                      CASE_INNER_LENGTH - 16, rim_t, rim_h,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation)
    rectangle_feature(comp, 'Lid rim rear', x_offset + inset + 8, outer_w - inset - rim_t, LID_THICKNESS,
                      CASE_INNER_LENGTH - 16, rim_t, rim_h,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation)
    rectangle_feature(comp, 'Lid rim left', x_offset + inset, inset + 8, LID_THICKNESS,
                      rim_t, CASE_INNER_WIDTH - 16, rim_h,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation)
    rectangle_feature(comp, 'Lid rim right', x_offset + outer_l - inset - rim_t, inset + 8, LID_THICKNESS,
                      rim_t, CASE_INNER_WIDTH - 16, rim_h,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # GPS cradle on the inside of the lid. The board slides under four flexible retaining lips.
    gps_x = x_offset + (outer_l - GPS_LENGTH) / 2
    gps_y = (outer_w - GPS_WIDTH) / 2
    rail_gap = GPS_WIDTH + 2 * CLEARANCE
    rail_h = GPS_MAX_HEIGHT + 1.0
    rectangle_feature(comp, 'GPS left clip', gps_x - 1.6, gps_y - CLEARANCE, LID_THICKNESS,
                      1.6, rail_gap, rail_h, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    rectangle_feature(comp, 'GPS right clip', gps_x + GPS_LENGTH + CLEARANCE, gps_y - CLEARANCE,
                      LID_THICKNESS, 1.6, rail_gap, rail_h,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation)
    rectangle_feature(comp, 'GPS end stop', gps_x, gps_y - CLEARANCE - 1.6, LID_THICKNESS,
                      GPS_LENGTH, 1.6, 2.5, adsk.fusion.FeatureOperations.JoinFeatureOperation)

    lip_z = LID_THICKNESS + GPS_MAX_HEIGHT
    for name, x in (('GPS upper clip left', gps_x - 1.6),
                    ('GPS upper clip right', gps_x + GPS_LENGTH - 2.0)):
        rectangle_feature(comp, name, x, gps_y + 3.0, lip_z,
                          3.6, GPS_WIDTH - 6.0, 1.2,
                          adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # Ventilation slots above the Pi.
    slot_count = 6
    slot_width = 6.0
    slot_pitch = 11.0
    slots_width = slot_width + (slot_count - 1) * slot_pitch
    slots_x = x_offset + (outer_l - slots_width) / 2
    for i in range(slot_count):
        rectangle_feature(comp, f'Vent slot {i + 1}', slots_x + i * slot_pitch, 12, 0,
                          slot_width, 2.2, LID_THICKNESS + 1,
                          adsk.fusion.FeatureOperations.CutFeatureOperation)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = app.activeProduct
        if not isinstance(design, adsk.fusion.Design):
            ui.messageBox('Open or create a Fusion 360 Design before running the script.')
            return

        root = design.rootComponent
        body_shell(root)
        lid(root, 110.0)
        app.activeViewport.fit()
        ui.messageBox('Case generated. Body and lid are separate bodies for STL export. '
                      'The SMA opening is aligned with the GPS cradle centreline.')
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    pass
