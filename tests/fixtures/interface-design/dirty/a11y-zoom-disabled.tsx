export function RootHead() {
  return (
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />{/* expect */}
      <meta name="theme-color" content="#0b0d10" />
    </head>
  );
}

export function LegacyHead() {
  return (
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1.0" />{/* expect */}
    </head>
  );
}

export function FineHead() {
  return (
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
    </head>
  );
}
