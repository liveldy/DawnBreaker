// Older Android WebView builds lack ES2022 Object.hasOwn, which is also
// used by dependencies during startup. Keep the standard own-property semantics.
if (!Object.hasOwn) {
  Object.defineProperty(Object, 'hasOwn', {
    value: (object: object, property: PropertyKey) => Object.prototype.hasOwnProperty.call(object, property),
    configurable: true,
    writable: true,
  });
}
