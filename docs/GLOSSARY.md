# Glossary of military and security terms

Plain-language definitions of the military, security and counter-drone terms used in Kairos Defense,
its screens and its documents, with how the app uses each one. Technical terms (DTW, PAA, RRF and so
on) are in the [user guide's glossary](USER_GUIDE.md#12-glossary). Everything in the app is
synthetic: the installations, actors, flights and reports are invented.

## Places and people

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Installation, base | A military site with a fenced perimeter and its own security force. | Twelve notional installations in three regions, named with the NATO phonetic alphabet (Alpha, Bravo, Charlie …). |
| Region | A group of installations in one area. | Each region has its own local map (meters east and north) and time zone. |
| Fence line, perimeter | The installation's boundary. | Most incidents begin as a drone approaches the fence; "inside the fence" matters for assessments. |
| Asset | Something inside the installation worth protecting, and so worth watching from the air. | Five per base: fuel farm, flight line, munitions area, headquarters, housing. A drone's *target* is the asset it lingers over. |
| Fuel farm | The installation's bulk fuel storage tanks. | The asset tonight's demo drone circles at Bravo. |
| Flight line | The area where aircraft are parked, fueled and launched. | Target of the "flight-line surveyor" (P2) and of swarm S1. |
| Munitions area | Where ammunition and explosives are stored. | Target of P3 and swarm S2. |
| BDOC | Base Defense Operations Center: the installation's security command post, staffed around the clock. | Writes the first log entry about an incident and its initial assessment (for example Delta's "hobbyist"). |
| Security forces (SF) | The installation's military police and guard force. | Patrol, observe and write reports (for example the white pickup on County Rd 12). |
| Base defense operator | The person on watch in the BDOC. | Uses Live watch and the Live page. |
| Analyst | Studies incidents and patterns across bases. | Uses the Match explainer, Case board and Swarm view; approves or rejects proposed links. |
| Investigator | Prepares material for referral or prosecution. | Builds and verifies evidence packages. |
| Watch officer, commander | Responsible for the security shift and its decisions. | Reads Shift delta; can close, reopen or escalate a case. |
| Drone operator, pilot | The person flying the drone. Not to be confused with the base defense operator. | Never identified: Kairos Defense links *flights*, never people. |

## Drones and the actors behind them

| Term | Meaning | In Kairos Defense |
|---|---|---|
| UAS, sUAS | Unmanned aircraft system: a drone with its controller and links. *Small* UAS are under 25 kg, like the drones here. | All flights in the app are small multirotor drones. |
| Counter-UAS (C-UAS) | Everything done to detect, track, identify and respond to hostile drones. | Kairos Defense covers the *identify and remember* part. It does not jam, capture or defeat drones. |
| Probing, prober | Flights that test or survey a base's defenses, usually by the same person again and again. A prober has stable habits. | Six synthetic probers, P1 to P6, each with a signature pattern, target, radio type and time of night. |
| Copycat | Someone whose flights look like another actor's but who is a different person. | C1 and C2 mimic P1 and P3; a good matcher must not confuse them (the "copycat-first" measure). |
| Hobbyist | A recreational flyer, the most common and usually harmless. | Random flights from parks and public events; the background noise. |
| Swarm | Several drones flown together as one coordinated group. | Teams S1 (five drones) and S2 (three drones), each with its own choreography. |
| Formation, choreography | How the drones of a swarm are arranged and the sequence of moves they fly. | Matched across bases and regions, even when flown at a different pace. |
| Line abreast | Drones side by side in a line, perpendicular to the direction of flight. | First move of S1's choreography. |
| V formation | Drones in a V shape. | Part of S1's choreography. |
| Trail | Drones one behind another. | Part of S2's choreography. |

## Detection and sensors

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Radar track | The series of positions a radar reports for one object, under one track number. | The raw material for matching; drawn as the drone's phosphor trail. |
| First contact, T+0 | The first time a sensor detects tonight's drone. | All demo times count from it (T+45 s, T+90 s …). |
| Air track symbol | The standard military map symbol for something in the air (MIL-STD-2525 symbology). | The live drone is drawn as an *unknown* air track: a four-lobed frame with a heading tick. |
| Radar shadow, terrain masking | Ground a sensor cannot see because terrain, trees or buildings block its line of sight. | Bravo has a wooded ridge to the northwest; the demo drone launches and is recovered in its shadow. |
| RF detection | A radio-frequency sensor hearing the drone's control or video link and measuring the direction it comes from. | The "RF" rows in the Stream; they keep an incident alive between radar hits. |
| RF family | The type of radio link a drone uses, a rough make-and-model fingerprint (FAM-07 …). | One factor in matching; never decisive on its own, because many drones share a family. |
| Remote ID (RID) | A broadcast that compliant drones transmit: a serial number, the drone's position and the operator's position. | "No Remote ID" is flagged in red: probers keep it off, and one actor spoofs it. |
| Spoofed Remote ID | A Remote ID broadcast with false information. | Used by P2. |
| Bearing | A direction in degrees clockwise from true north. | Approach and departure directions, RF bearings. |
| Sensor outage, dropout | A gap in detections, from a sensor fault or the target leaving coverage. | Partial tracks are matched anyway. |

## Flight behavior

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Launch point | Where the drone took off. | Often near a road or park; an input to matching when it was seen. |
| Approach | The drone's path from launch toward its target; the *approach bearing* is the direction it came from. | Compared between flights after aligning each to its own target. |
| Loiter | Lingering over or near a target: hovering, circling or sweeping. | How the app decides what the target is. |
| Orbit | Circling a point at a steady radius, clockwise or counter-clockwise. | P1's signature: a 180 m counter-clockwise orbit over the fuel farm. |
| Lawnmower | A back-and-forth sweep that covers an area, as in a survey. | P2 over the flight line. |
| Perimeter run | Flying along the fence at a fixed distance. | P4. |
| Hover and stare | Holding still over one point to watch it. | P5 over headquarters. |
| Egress | The drone leaving the area after its task. | One of the three flight phases the app shows: approach, loiter, egress. |
| Recovery point | Where the drone lands at the end of the flight and the operator picks it up. | Known for past flights whose landing was seen. |
| Recovery zone | The area where the drone is predicted to land and be picked up. Because small drones are recovered close to their operator, it shows where to send a patrol. | Forecast from how the best-matching past flights ended: drawn as a dotted circle (center, radius) with the roads that cross it, plus a dashed predicted exit path. In the demo it lies about 2.1 km northwest of Bravo's fuel farm, on County Rd 12, inside the radar shadow. |
| Exit path | The predicted route from the drone's current position to the recovery zone. | The dashed line in the theater. |

## Reports and intelligence

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Incident | One detected event at one installation: a single flight or a swarm. | Starts at first detection; the unit the matcher compares. |
| Report | A written account of an incident. | Four sources: BDOC log, security forces report, local police report, aviation authority (FAA) summary. |
| Source grade (A1 to F6) | The NATO "Admiralty" grading of a report. The letter is how reliable the source is (A completely reliable, B usually reliable, C fairly reliable, D not usually reliable, E unreliable, F cannot be judged). The digit is how credible the information is (1 confirmed, 2 probably true, 3 possibly true, 4 doubtful, 5 improbable, 6 cannot be judged). | For example the planted Delta security forces report is graded B2: a usually reliable source, probably true. |
| Clue | A detail in a report that can link incidents. | A vehicle's color and type (never a plate), a road, lights, sound, the launch site, the direction of departure. |
| Assessment | A base's judgement of what an incident was. | Labels: hobbyist, unknown, probing, swarm. Delta's April "hobbyist" assessment was wrong, which is the point of the demo. |
| Attribution | Saying which known actor or pattern an incident belongs to. | Matches start "open, unattributed" until an analyst approves a link. |

## Case handling and evidence

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Case | A set of incidents believed to be the same pattern, managed together. | Kept in the case memory and shown on the Case board. |
| Link, proposal | A suggestion that two incidents belong to the same case. | The matcher only proposes; an analyst approves or rejects. |
| Contradiction | Two current claims about a case that disagree. | Outlined in red (for example "hobbyist" against "probing"); never resolved automatically. |
| Known then, known now | What was known about a case at a past moment, against what is known today. | The Case board's two views; Delta's April decision looks different once later flights are linked. |
| Escalate | Refer a case up the chain of command. | One of the case decisions, behind a confirm. |
| Notify law enforcement | Hand a case to civilian police or federal authorities, who usually handle drone operators outside the fence. | One of the case decisions, behind a confirm. |
| Evidence package | A bundle of a case's records prepared for referral or prosecution. | Exported only after approval, signed, and verifiable by anyone. |
| Chain of custody | Proof that evidence has not been altered since it was collected. | Provided by the hash-chained ledger and the package's signature and per-file hashes. |
| Shift delta, shift brief | What changed since the last shift, for the handover. | The Shift delta page. |

## Live mode

| Term | Meaning | In Kairos Defense |
|---|---|---|
| Sensor feed | The stream of detections that sensors send to a command system. | In live mode a separate simulator plays the sensors; a real radar or RF adapter would use the same ingest interface. |
| Scenario | A planned situation flown for training or a demonstration. | Returning prober, copycat, hobbyist, swarm repeat, new operator twice. |
| Reveal | After the event, telling the audience who really flew. | "Reveal who flew" on a closed live incident, served by the evaluation code; the app never knows while the flight is live. |
