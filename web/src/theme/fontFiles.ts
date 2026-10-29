// The .woff files for 3D labels: troika (drei <Text>) does not read woff2, and without a font it
// would fetch one from a CDN (rule 5). Bundled by Vite from @fontsource, served from our origin.
import b612 from "@fontsource/b612/files/b612-latin-400-normal.woff?url";
import b612Bold from "@fontsource/b612/files/b612-latin-700-normal.woff?url";
import b612Mono from "@fontsource/b612-mono/files/b612-mono-latin-400-normal.woff?url";

export const FONT_UI = b612;
export const FONT_UI_BOLD = b612Bold;
export const FONT_DATA = b612Mono;
