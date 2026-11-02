// 3D positions and sizes of warehouse objects. x runs along an aisle, y up, and z across aisles.
// Spacing across aisles is for display only, as the simulation does not define it.

const BLOCK_GAP_SHARE = 0.1;

export function createLayout(layout) {
  const { aisle_count, racks_per_aisle, bays_per_rack, levels_per_rack, cell } = layout;
  const aisleWidth = cell.width_m;
  const blockWidth = racks_per_aisle * cell.width_m + aisleWidth;
  const blockGap = BLOCK_GAP_SHARE * cell.width_m;
  const length = bays_per_rack * cell.length_m;
  const height = levels_per_rack * cell.height_m;
  const rackOffset = (aisleWidth + cell.width_m) / 2;

  const aisleCenterZ = (aisle) => (aisle - 1) * (blockWidth + blockGap);
  const rackZ = (aisle, rack) => aisleCenterZ(aisle) + (rack === 1 ? -rackOffset : rackOffset);

  return {
    aisleCount: aisle_count,
    racksPerAisle: racks_per_aisle,
    bays: bays_per_rack,
    levels: levels_per_rack,
    cell,
    aisleWidth,
    blockWidth,
    blockGap,
    length,
    height,
    cellCount: aisle_count * racks_per_aisle * bays_per_rack * levels_per_rack,
    aisleCenterZ,
    rackZ,
    endX: (end) => (end === "left" ? 0 : length),
    craneWorldPosition: (aisle, [horizontal, vertical]) => [
      horizontal,
      vertical,
      aisleCenterZ(aisle),
    ],
    cellBox: ([aisle, rack, bay, level]) => ({
      center: [
        (bay - 0.5) * cell.length_m,
        (level - 1) * cell.height_m + cell.height_m / 2,
        rackZ(aisle, rack),
      ],
      size: [cell.length_m, cell.height_m, cell.width_m],
    }),
    bounds: () => ({
      min: [0, 0, aisleCenterZ(1) - aisleWidth / 2 - cell.width_m],
      max: [
        length,
        height,
        aisleCenterZ(aisle_count) + aisleWidth / 2 + (racks_per_aisle === 2 ? cell.width_m : 0),
      ],
    }),
  };
}
