import { localDay, localHM } from "../director/captions";

/** A readable local time: "Apr 20, 09:10 local" at an offset from UTC (hours). */
export function localStamp(iso: string, offsetH: number): string {
  return `${localDay(iso, offsetH) ?? ""}, ${localHM(iso, offsetH) ?? ""} local`;
}
