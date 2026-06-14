/**
 * Build helper for the n8n community node package.
 *
 * `npm run build` runs `tsc` (which compiles the TypeScript to `dist/`) and then
 * `gulp build:icons`, which copies the node SVG icons next to their compiled
 * `*.node.js` files so n8n can resolve `icon: 'file:oabp.svg'` at runtime.
 * (Icons are not handled by tsc.)
 */

const { src, dest } = require('gulp');

function buildIcons() {
  return src('nodes/**/*.{png,svg}').pipe(dest('dist/nodes'));
}

exports['build:icons'] = buildIcons;
exports.default = buildIcons;
