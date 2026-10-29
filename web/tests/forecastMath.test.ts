import { describe, expect, it } from "vitest";

import { forecastPlace } from "../src/director/captions";
import { zoneLabel, zoneRoads } from "../src/three/forecastLayer";
import {
  clipPolylineToCircle,
  compass8,
  distanceBearing,
  midpointAlong,
  pointInPolygon,
  pointInPolygons,
  roughDistance,
} from "../src/three/forecastMath";
import type { Vec2 } from "../src/three/sceneMath";
import { SCENE, T105 } from "./real";

describe("forecast geometry (§13, D-132)", () => {
  it("clips a polyline to a circle", () => {
    // a chord straight through
    expect(
      clipPolylineToCircle(
        [
          [-20, 0],
          [20, 0],
        ],
        [0, 0],
        10,
      ),
    ).toEqual([
      [
        [-10, 0],
        [10, 0],
      ],
    ]);
    // a tangent touch is a miss
    expect(
      clipPolylineToCircle(
        [
          [-20, 10],
          [20, 10],
        ],
        [0, 0],
        10,
      ),
    ).toEqual([]);
    // partly inside: in at the boundary, the inside vertex, out at the boundary
    const parts = clipPolylineToCircle(
      [
        [-20, 0],
        [0, 5],
        [0, 30],
      ],
      [0, 0],
      10,
    );
    expect(parts).toHaveLength(1);
    expect(parts[0]?.[1]).toEqual([0, 5]);
    expect(Math.hypot(...(parts[0]?.[0] as Vec2))).toBeCloseTo(10);
    expect((parts[0]?.at(-1) as Vec2)[1]).toBeCloseTo(10);
    // starting inside
    expect(
      clipPolylineToCircle(
        [
          [0, 0],
          [20, 0],
        ],
        [0, 0],
        10,
      ),
    ).toEqual([
      [
        [0, 0],
        [10, 0],
      ],
    ]);
  });

  it("matches the CLI on the T+105 forecast: 2,164 m northwest of the fuel farm", () => {
    const farm = SCENE.assets.find((a) => a.asset_id === "BRAVO-fuel_farm");
    if (!farm) throw new Error("no fuel farm");
    const f = T105.forecast;
    const d = distanceBearing([farm.centroid_x_m, farm.centroid_y_m], [f.center_x_m, f.center_y_m]);
    expect(Math.abs(d.distance - 2164)).toBeLessThanOrEqual(1);
    expect(Math.abs(d.bearing - 320)).toBeLessThanOrEqual(1);
    expect(compass8(d.bearing)).toBe("northwest");
    expect(roughDistance(d.distance)).toBe("2.2 km");
    const p = forecastPlace(f, SCENE);
    expect(p?.shadow).toBe(true); // the zone center sits in Bravo's radar shadow
    expect(zoneLabel(f, SCENE)).toBe("Predicted recovery zone, 2.2 km northwest, from 3 matches");
  });

  it("finds County Rd 12's in-zone segment at T+105", () => {
    const roads = zoneRoads(T105.forecast, SCENE);
    expect(roads.map((r) => r.name)).toEqual(["County Rd 12"]);
    const f = T105.forecast;
    for (const p of roads[0]?.parts.flat() ?? [])
      expect(Math.hypot(p[0] - f.center_x_m, p[1] - f.center_y_m)).toBeLessThanOrEqual(
        f.radius_m + 1e-6,
      );
    expect(roads[0]?.mid).not.toBeNull();
  });

  it("names compass points the way Python's sim/lexicon.compass8 does", () => {
    expect(compass8(0)).toBe("north");
    expect(compass8(22.4)).toBe("north");
    expect(compass8(22.5)).toBe("northeast");
    expect(compass8(315)).toBe("northwest");
    expect(compass8(337.5)).toBe("north");
    expect(compass8(-10)).toBe("north");
    expect(compass8(180)).toBe("south");
  });

  it("tests points in polygons and finds a polyline's midpoint", () => {
    const sq: Vec2[] = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [0, 0],
    ];
    expect(pointInPolygon([5, 5], sq)).toBe(true);
    expect(pointInPolygon([15, 5], sq)).toBe(false);
    expect(
      pointInPolygons(
        [18, 2],
        [
          sq,
          [
            [12, 0],
            [20, 0],
            [20, 10],
          ],
        ],
      ),
    ).toBe(true);
    expect(
      pointInPolygons(
        [15, 5],
        [
          sq,
          [
            [12, 0],
            [20, 0],
            [20, 10],
          ],
        ],
      ),
    ).toBe(false);
    expect(
      midpointAlong([
        [0, 0],
        [10, 0],
        [10, 10],
      ]),
    ).toEqual([10, 0]);
    expect(roughDistance(368)).toBe("370 m");
  });
});
