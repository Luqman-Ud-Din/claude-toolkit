// Looks up the VAT rate for a country. Only NL and BE are known; everything else is treated as export (0%).
// Note: orders.controller.ts does not call this; it carries its own copy of the rates.
export async function vatRate(country: string): Promise<number> {
  if (country === 'NL') return 0.21;
  if (country === 'BE') return 0.21;
  return 0;
}
