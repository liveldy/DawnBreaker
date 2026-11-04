# Third-party components

DawnBreaker is distributed under AGPL-3.0-or-later. Existing copyright notices and the following upstream licenses remain in effect.

| Component | Pinned source | License | Use |
|---|---|---|---|
| Mihomo | [v1.19.33](https://github.com/MetaCubeX/mihomo/tree/v1.19.33) | GPL-3.0 | Unmodified Windows core executable |
| libmihomo-android | [v0.3.13](https://github.com/oviron/libmihomo-android/tree/v0.3.13) | GPL-3.0 | Unmodified Android JNI AAR, including Mihomo v1.19.33 |
| LinkSwift | [v1.1.3](https://github.com/hmjz100/LinkSwift/tree/v1.1.3) | AGPL-3.0-or-later | Unmodified userscript; DawnBreaker supplies a separate GM adapter |
| last-token model-atlas | [source](https://github.com/liveldy/last-token/tree/main/model-atlas) | GPL-3.0 | Adapted dataset normalization in `src/atlasData.ts`; chart and UI rewritten |
| jQuery | 3.6.0 | MIT | LinkSwift dependency |
| SweetAlert2 | 11.4.8; theme-dark 5.0.26 | MIT | LinkSwift dependency |
| js-md5 | 0.7.3 | MIT | LinkSwift dependency |
| js-sha256 | 0.11.1 | MIT | LinkSwift dependency |

See adjacent license files and `linkswift/integrity.json`. Other npm/Python/Gradle dependencies retain their own licenses and notices, available in their installed distributions. `fflate` and `yaml` retain notices in the generated desktop vendor bundle.

Corresponding core source archives and build instructions are provided with application releases. The app repository contains all DawnBreaker source, including the GM adapter, Java/JNI integration and build configuration. Native binaries are downloaded by `scripts/fetch_native_components.py`, which verifies pinned SHA256 hashes; they are excluded from source control.

The optional `mods/` media packs (Riot Games images/voices, music, word lists and character artwork) are user-supplied, separately copyrighted material. They are not covered by DawnBreaker's software license and are excluded from this source repository. The program works without these packs, with empty media catalogs and built-in sample words.
