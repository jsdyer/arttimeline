# Art Timeline

A browser collection explorer for [CoolCode](https://coolcode.ca/), using The Metropolitan Museum of Art and Art Institute of Chicago's public collection data.

Search for an artist, place or subject; page through the museums' results; filter the loaded works by material, place, museum and overlapping date range; and compare any two works with their original records and credits. Download the visible records as CSV or the comparison as JSON. No account or key is needed.

<!-- coolcode:guide -->
Search either museum with your own terms, then refine the loaded works and compare two objects with their original date labels and credits. The opening collection and search presets are editable in web/config.json; they do not limit live searches.
<!-- /coolcode:guide -->

## Try it

1. The opening collection loads immediately from a dated bundled snapshot.
2. Type any term such as `moonlight` or `Japanese prints` and choose one or both museums. Search fetches actual museum API records.
3. **Load next museum results** expands the current result set. Filters and the timeline describe loaded records only, not the entire museum collection.
4. Refine by artist/material/place, choose a museum, and optionally enter years. Negative years mean BCE. Date ranges match when they overlap your selected years.
5. Use **Inspect work** for its metadata and source, or **Compare** on two works. Adding a third replaces the oldest selection. Exports remain local.

## Expand or customize

Edit [`web/config.json`](web/config.json), which is copied into the published site:

- `presets`: any number of suggested searches. For example, append `"early photography"` to add a button.
- `defaultQuery`: the text initially shown in the search box. Visitors can always replace it.
- `pageSize`: records requested from each museum per click, 1–100. Default 12 keeps Met detail requests modest. Museum pagination ceilings still apply.
- `baseline.metObjectIds` and `baseline.aicObjectIds`: any number of valid numeric museum artwork IDs for the opening collection. For example, add `359362` to the Met array and run the refresh. Nothing in the gallery or validation requires a particular number of works.
- `requestTimeoutMs`, `metDetailDelayMs`, and `aicUserAgent`: request settings and a public collector contact string (not a secret).

Changing presets or page size needs only a normal commit/push to `main`; GitHub Actions checks and publishes it. Changing opening artwork IDs also requires **Actions → Art Timeline · Check and publish → Run workflow → Refresh the opening collection**. That reads the latest config and commits/publishes a validated replacement. Alternatively run `node scripts/refresh.mjs`, review the changed `web/data/collection.json`, and commit it together with the config. A failure leaves the previous collection intact.

There is no automatic refresh schedule: artwork metadata is relatively stable, and live search already requests current records. The manual collection refresh is explicit. Its capture time is retrieval time, not the object's creation date or museum update time.

Adding another museum requires a provider adapter in `web/model.mjs` / `web/app.mjs`, because museums have different schemas and rights fields. Defaults, queries, IDs and supported page sizes need no application-code changes.

## Sources, reuse and coverage

- [The Met Collection API](https://metmuseum.github.io/) supplies object metadata and images explicitly marked `isPublicDomain: true`. Uses the current `/public/collection/v1.1/search` endpoint and preserves object date labels. Search returns object IDs, requiring individual detail requests; one failed detail is reported instead of destroying the whole search.
- [Art Institute of Chicago API](https://api.artic.edu/docs/) supplies collection metadata, public-domain flags and IIIF image identifiers. The app asks for selected fields. The collector sends the museum's requested `AIC-User-Agent` contact header; browser searches use an ordinary credential-free CORS GET because the optional header triggers a preflight currently challenged by the museum's edge service. The Chicago query requires the search words to match catalogue fields as well as requiring the public-domain flag; it does not merely boost matches within all public-domain objects. Default page size stays small. The museum API allows anonymous access, but may throttle or block particular clients.
- Opening Chicago records may come from the museum's [published API-data preview](https://github.com/art-institute-of-chicago/api-data) if the live API is unavailable during collection. Each such record preserves `retrievedFrom`, `sourceKind` and `sourceUpdatedAt`. The preview is a limited, potentially older publication; its fetch date does **not** claim current museum metadata. For IDs absent from that preview, a failed live fetch stops the refresh and preserves the last good collection.
- Images load from the original museum servers only when the individual record explicitly marks them public domain. No image permission is inferred from age. Metadata-only records remain inspectable. Credit lines and source links stay with the works. [Met terms](https://www.metmuseum.org/policies/terms-and-conditions), [Chicago image licensing](https://www.artic.edu/image-licensing), [Chicago terms](https://www.artic.edu/terms).
- Museum collection metadata used here is CC0. Chicago descriptions, which have separate attribution terms, are not included. This app is independent and does not imply museum endorsement.

The century chart counts loaded objects by the midpoint of their date range. It is not a measure of historical art production, collection completeness or popularity. Date filters use ranges, not midpoint dates. Missing dates are excluded from the chart. Culture, nationality and place fields can reflect different catalogue conventions.

## Privacy

Museum searches send query text directly to the selected provider. Images load from museum hosts, which receive normal network information. Filters, selected comparisons and exports are processed in the browser. The app does not persist them in local storage or send them to CoolCode. The shared CoolCode visit counter and issue-report link are included by the builder.

## Develop

The build uses only Python's standard library; model tests and the optional collector require modern Node.js.

```sh
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

`dist/` is generated and ignored. Application source lives under `web/`. The normal build is offline. GitHub Actions runs the browser smoke test after the unit/build checks, and publishes successful `main` builds to GitHub Pages. No CNAME or credentials are part of the app.


## Verification notes

The opening records, comparisons, exports and Met live custom searches were checked in the browser. Chicago records and the matching live search query succeeded through the normal collector, but Chicago live search returned a network failure in the cloud browser used for this build, even after removing the optional preflight-triggering header. This does not establish a failure for every visitor. Chicago remains enabled; if a request fails, existing works remain usable and the page offers the same query on Chicago's own collection site. No proxy, authentication change or access-control workaround is used.
