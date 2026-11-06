# Third-party components

DawnBreaker is distributed under AGPL-3.0-or-later. Existing copyright notices and the following upstream licenses remain in effect.

| Component | Pinned source | License | Use |
|---|---|---|---|
| Mihomo | [v1.19.33](https://github.com/MetaCubeX/mihomo/tree/v1.19.33) | GPL-3.0 | Unmodified Windows core executable |
| libmihomo-android | [v0.3.13](https://github.com/oviron/libmihomo-android/tree/v0.3.13) | GPL-3.0 | Unmodified Android JNI AAR, including Mihomo v1.19.33 |
| LinkSwift | [v1.1.3](https://github.com/hmjz100/LinkSwift/tree/v1.1.3) | AGPL-3.0-or-later | Unmodified userscript; DawnBreaker supplies a separate GM adapter |
| last-token model-atlas | [source](https://github.com/liveldy/last-token/tree/main/model-atlas) | GPL-3.0 | Adapted dataset normalization in `src/atlasData.ts`; chart and UI rewritten |
| MetaCubeX meta-rules-dat | [source and data origins](https://github.com/MetaCubeX/meta-rules-dat) | GPL-3.0; upstream data notices apply | Pinned country.mmdb, geoip.dat and geosite.dat, bundled for first-start initialization; hashes and source commit in `geodata/manifest.json` |
| holiday-cn | [source](https://github.com/NateScarlet/holiday-cn) | MIT | Published mainland China holiday schedules, government references retained in `server/calendar-data` |
| Pandoc | [source](https://github.com/jgm/pandoc) | GPL-2.0-or-later | Separately installed server executable for Word / OMML to Markdown / LaTeX; not bundled with clients |
| LibreOffice Writer / Math | [source](https://github.com/LibreOffice/core) | MPL-2.0; upstream notices apply | Separately installed server programs for legacy DOC conversion; not bundled with clients |
| python-docx | [source](https://github.com/python-openxml/python-docx) | MIT | Development-only synthetic Word fixtures |
| jQuery | 3.6.0 | MIT | LinkSwift dependency |
| SweetAlert2 | 11.4.8; theme-dark 5.0.26 | MIT | LinkSwift dependency |
| js-md5 | 0.7.3 | MIT | LinkSwift dependency |
| js-sha256 | 0.11.1 | MIT | LinkSwift dependency |

See adjacent license files and `linkswift/integrity.json`. Other npm/Python/Gradle dependencies retain their own licenses and notices, available in their installed distributions. `fflate` and `yaml` retain notices in the generated desktop vendor bundle.

Corresponding core source archives and build instructions are provided with application releases. The app repository contains all DawnBreaker source, including the GM adapter, Java/JNI integration and build configuration. Native binaries are downloaded by `scripts/fetch_native_components.py`, which verifies pinned SHA256 hashes; they are excluded from source control.

Run `python scripts/fetch_geodata.py` before either native build. Geography data is downloaded into `.tooling/geodata` only after size and SHA256 verification, then copied into both native packages. Existing valid device caches are retained. The release source bundle includes the geography snapshot, upstream build source and notices. `geodata/README.md` lists the data projects used upstream and their respective notices.

The optional `mods/` media packs (Riot Games images/voices, music, word lists and character artwork) are user-supplied, separately copyrighted material. They are not covered by DawnBreaker's software license and are excluded from this source repository. The program works without these packs, with empty media catalogs and built-in sample words.
