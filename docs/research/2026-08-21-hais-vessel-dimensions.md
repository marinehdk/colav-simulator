# HAIS vessel-dimension provenance for the 2026-07-01 benchmark

## Decision

For the three requested MMSIs, use the Norwegian Maritime Authority (Sjøfartsdirektoratet, SDIR) measurement-certificate values as the formal `Ship Domain` dimensions:

- `length_m` = SDIR `srMeasurementData.overallLength.value` (LOA).
- `beam_m` = SDIR `srMeasurementData.width.value` (breadth).
- Keep the measurement document date, journal date, SDIR vessel ID, IMO, and call sign beside the dimensions.
- Use Kystdatahuset's public NSR lookup only for the MMSI-to-IMO/call-sign identity bridge and as a cross-check.
- Treat Kystdatahuset AIS `breadth=0` as unavailable evidence, not as a zero-width vessel.

The three dimension records are dated before `T0 = 2026-07-01`. The current SDIR responses report all three vessels as active when queried on 2026-08-21, but the APIs do not provide a historical snapshot query. The benchmark should therefore record the measurement and registry dates explicitly and describe the result as “latest conferred measurement available before T0,” not as an independently proven historical database snapshot.

## Retrieval and source policy

Retrieved 2026-08-21, Asia/Shanghai (the Kystdatahuset HTTP responses were dated 2026-08-21 UTC). Only first-party sources were used:

- [Kystverket HAIS documentation](https://hais.kystverket.no/about) — HAIS scope, Parquet columns, open-data terms, and AIS-quality caveats. [S1]
- [Kystdatahuset OpenAPI](https://kystdatahuset.no/ws/swagger/v1/swagger.json) and [Swagger UI](https://kystdatahuset.no/ws/swagger/index.html) — official Kystverket API contracts and field names. [S2]
- [Kystverket/NCA NSR lookup endpoint](https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos) — public response for the three MMSIs. [S3]
- [Sjøfartsdirektoratet ship-register page](https://www.sdir.no/en/the-norwegian-ship-registers/) and [official ship-search application](https://skipssok.sdir.no/) — register authority and search surface. [S4]
- SDIR ship-search API responses, linked below per vessel, including the conferred measurement records. [S5–S7]
- [SDIR guidance on measurement of greatest length](https://www.sdir.no/regelverk/rundskriv/veiledning-om-maling-av-storste-lengde-pa-skip/) — LOA/“greatest length” terminology. [S8]

No VesselFinder, MarineTraffic, Wikipedia, commercial vessel database, or search-result snippet was used.

## Recommended dimensions and identity

| MMSI | IMO | Call sign | Identity / register | SDIR vessel ID | `length_m` (LOA) | `beam_m` | Measurement date | Journal date | Type evidence |
|---:|---:|---|---|---:|---:|---:|---|---|---|
| 257252000 | 9793662 | LDZS | FREYJA; NOR; active | 93640 | 84.6 | 16.0 | 2017-06-26 | 2017-09-15 | SDIR `BRØNNFARTØY`; Kystdatahuset `Fish Carrier` |
| 258764000 | 9331098 | JXPT | PELAGIA HORDAFOR; NOR; active | 106419 | 59.2 | 10.8 | 2022-09-21 | 2022-09-27 | SDIR `TANKSKIP: OLJE`; Kystdatahuset `Bunkering Tanker (Oil)` |
| 259189000 | 9802619 | LEDI | VALDERØY; NOR; active | 94133 | 32.0 | 8.8 | 2016-12-20 | 2017-01-11 | SDIR `KATAMARAN PASSASJER`; Kystdatahuset `Passenger Ship` |

The Kystdatahuset NSR response independently returned the same MMSI, IMO, call sign, length, breadth, vessel name, and Norwegian flag for all three vessels. Its `modifieddate` values were 2026-04-22 (FREYJA), 2023-12-01 (PELAGIA HORDAFOR), and 2024-03-11 (VALDERØY), all before T0.

## Per-vessel provenance

### MMSI 257252000

Kystdatahuset NSR returned `mmsino=257252000`, `imono=9793662`, `callsign=LDZS`, `shipname=FREYJA`, `length=84.599998...`, `breadth=16`, flag `NOR`, and type `Live Fish Carrier (Well Boat)`. The SDIR search by IMO returned active NOR vessel `vesselId=93640`, call sign `LDZS`, name `FREYJA`; its conferred `MÅLEBREV` contains `overallLength=84.6 m`, `width=16.0 m`, and measurement date `2017.06.26` (journal date `2017.09.15`). [S3] [S5]

- [SDIR search response by IMO 9793662](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-list-nis-nor?searchText=9793662&language=no)
- [SDIR vessel data 93640](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/93640?language=no)

### MMSI 258764000

Kystdatahuset NSR returned `mmsino=258764000`, `imono=9331098`, `callsign=JXPT`, `shipname=PELAGIA HORDAFOR`, `length=59.200000...`, `breadth=10.800000...`, flag `NOR`, and type `Bunkering Tanker`. The SDIR search returned active NOR vessel `vesselId=106419` with the same IMO and call sign. Its conferred `MÅLEBREV` contains `overallLength=59.2 m`, `width=10.8 m`, and measurement date `2022.09.21` (journal date `2022.09.27`). [S3] [S6]

- [SDIR search response by IMO 9331098](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-list-nis-nor?searchText=9331098&language=no)
- [SDIR vessel data 106419](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/106419?language=no)

### MMSI 259189000

Kystdatahuset NSR returned `mmsino=259189000`, `imono=9802619`, `callsign=LEDI`, `shipname=VALDEROY`, `length=32`, `breadth=8.800000...`, flag `NOR`, and type `Passenger Ship`. The SDIR search returned active NOR vessel `vesselId=94133`, call sign `LEDI`, name `VALDERØY`; its conferred `MÅLEBREV` contains `overallLength=32.0 m`, `width=8.8 m`, and measurement date `2016.12.20` (journal date `2017.01.11`). The spelling difference is Norwegian `Ø` versus the ASCII registry/API spelling `O`. [S3] [S7]

- [SDIR search response by IMO 9802619](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-list-nis-nor?searchText=9802619&language=no)
- [SDIR vessel data 94133](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/94133?language=no)

## Exact API requests

### Kystdatahuset NSR identity bridge

```http
POST https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos
Content-Type: application/json

{"mmsi":[257252000,258764000,259189000],"imo":[],"callsign":[]}
```

The successful response contained the three records summarized above. This is the NSR endpoint, not the restricted Fairplay/Shipinfo endpoint.

### Kystdatahuset AIS static cross-check

```http
POST https://kystdatahuset.no/ws/api/ais/statinfo/for-mmsis-time
Content-Type: application/json

{"mmsiIds":[257252000,258764000,259189000],"start":"202607010000","end":"202607012359"}
```

This response identified all three vessels and returned lengths `84.6`, `59.2`, and `32`, but returned `breadth: 0` for each. The OpenAPI schema marks `breadth` nullable but does not define zero as a valid physical width or document a zero sentinel. Because the same official NSR records provide nonzero breadth, the AIS-static breadth values are classified `UNAVAILABLE/SENTINEL`, not used for Ship Domain geometry. [S2] [S3]

### Local HAIS file check

The user-provided archive is:

```text
/Users/marine/Downloads/浏览器下载/Hais_e716cfac-348c-417b-acbd-04a228732de7.zip
```

The selected entry `hais_2026-07-01.snappy.parquet` contains the three MMSIs (observed-row counts in that file: 5,318; 10,837; and 11,052 respectively). Its schema contains time, MMSI, position, navigation status, COG, heading, SOG, ROT, manoeuvre, source, AIS class, message type, and geometry. It does not contain length, breadth/beam, IMO, name, or vessel type. This matches the official HAIS column documentation, which lists `mmsi` as the transponder identity and warns that transponder-reported vessel characteristics can be missing or incorrectly configured. [S1]

No full-archive scan was performed; only the single 2026-07-01 entry and the requested MMSI projection were inspected.

## Benchmark integration rule

Store one immutable dimension record per actor:

```text
dimensions_source = "SDIR_NOR_measurement_certificate"
length_m = overallLength.value
beam_m = width.value
measurement_date = measurement-document.date
registry_journal_date = measurement-document.journalDate
mmsi = Kystdatahuset NSR mmsino
imo = Kystdatahuset NSR imono / SDIR IMO
```

Use the SDIR `overallLength`/`width` pair for the formal Ship Domain and record Kystdatahuset AIS `length`/`breadth` as separate comparison evidence only. Do not silently replace missing dimensions with defaults, and do not interpret `breadth=0` as a physical value.

For the 2026-07-01 Historical AIS Counterfactual Benchmark, the three records are suitable as dimension provenance because their conferred measurement dates and journal dates precede T0. The remaining limitation is temporal: the public SDIR lookup returned the current registry view on 2026-08-21 rather than an explicit as-of-T0 version. Preserve the query date and both document dates in the case manifest.

## Licensing and reuse boundary

Kystverket states that open HAIS data are free and available under the Norwegian Licence for Open Government Data (NLOD), subject to its coverage/privacy exclusions. [S1] The queried NSR endpoint returned data without authentication; the Kystdatahuset API documentation separately identifies licensed Fairplay/Shipinfo datasets and restricted endpoints. [S2] This note stores derived dimensions, identifiers, source URLs, query payloads, and dates rather than redistributing a registry dump. Confirm any redistribution or commercial reuse requirement with Kystverket/SDIR before shipping raw registry responses.

## Source ledger

| ID | First-party source | Used for |
|---|---|---|
| S1 | [hais.kystverket.no/about](https://hais.kystverket.no/about) | HAIS columns, scope, NLOD, AIS quality caveats |
| S2 | [Kystdatahuset Swagger JSON](https://kystdatahuset.no/ws/swagger/v1/swagger.json) | API paths, request schemas, response field semantics, access notes |
| S3 | [Kystdatahuset NSR endpoint](https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos) | MMSI/IMO/call-sign identity, NSR dimensions, type, flag, modified date |
| S4 | [SDIR register overview](https://www.sdir.no/en/the-norwegian-ship-registers/) | Register authority and public ship-search scope |
| S5 | [SDIR vessel data 93640](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/93640?language=no) | FREYJA conferred measurement |
| S6 | [SDIR vessel data 106419](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/106419?language=no) | PELAGIA HORDAFOR conferred measurement |
| S7 | [SDIR vessel data 94133](https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/94133?language=no) | VALDERØY conferred measurement |
| S8 | [SDIR measurement guidance](https://www.sdir.no/regelverk/rundskriv/veiledning-om-maling-av-storste-lengde-pa-skip/) | LOA/greatest-length terminology |
