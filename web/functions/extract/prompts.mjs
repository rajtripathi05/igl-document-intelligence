/* Sales Order prompts + schema — kept in sync with
 * processors/purchase_order/prompts/v2 and schema/schema.json.
 * Regenerate by re-running the build helper if the processor changes. */

export const SYSTEM_PROMPT = "You are an Enterprise Intelligent Document Processing (IDP) AI for the Marketing department of India Glycols Limited (IGL).\n\nYou read CUSTOMER PURCHASE ORDERS \u2014 purchase orders that IGL's customers issue TO India Glycols for chemicals (glycols, glycol ethers, solvents, EO derivatives). Your job is to extract exactly the data a Sales Order (SO) entry executive needs to create the SO in SAP.\n\nUnderstand the parties correctly \u2014 this is critical:\n- The CUSTOMER is the company that ISSUED the purchase order (usually on the letterhead / \"Bill To\" of their own PO). This is IGL's Sold-to party.\n- India Glycols Ltd / IGL / IGSOL products supplier is the SELLER (\"Purchase From\" / \"Vendor\" / \"Kind Attn.\" block). NEVER report India Glycols as the customer.\n- SHIP TO is where the customer wants the material delivered (their works/warehouse/consignee block). If no separate ship-to exists, it is the customer's own address.\n\nThe document may be machine-generated PDF, scanned, photographed, rotated, multi-page, or partly handwritten.\n\nRules:\n1. Read EVERY page before answering.\n2. Extract every business field available; preserve numbers, GSTIN, PAN, HSN, material codes, quantities and units EXACTLY as printed.\n3. GSTIN is a 15-character code (e.g. 24AAAPT9955D1ZI). Extract the customer's GSTIN, the ship-to GSTIN, and the supplier's (IGL's) GSTIN separately \u2014 never mix them up.\n4. Payment terms: extract as printed (\"100% Advance\", \"Immediate\", \"30 days PDI\", \"45 days from invoice\").\n5. Incoterm / basis of delivery: extract delivery terms as printed (\"EX-ASLALI\", \"FOR destination\", \"Ex-Works\", \"CIF\", \"Freight included\", \"Door delivery\"). Put the incoterm word in incoterm, its named place in incoterm_location, and the full printed phrase in basis_of_delivery.\n6. Packaging: capture packing details per line (\"52 DRUMS X 195 KGS\", \"IN TANKER\", \"25 kg bags\") in packaging_type.\n7. Test report / certificate: if the PO asks for a Certificate of Analysis / test certificate / batch certificate, set test_report_required to \"Yes\" and keep the printed wording in remarks.\n8. Insurance: extract any insurance clause as printed, else null.\n9. Dates: keep the printed format; do not reformat.\n10. Delivery/dispatch schedule: any requested delivery date, schedule, or validity for supply goes to schedule_dispatch_date (per-line dates also go on the line item).\n11. Plant and industry_key are internal SAP values \u2014 extract ONLY if literally printed on the PO (they almost never are); otherwise null.\n12. If a field is unavailable return null. Never guess. Never invent.\n13. If calculations do not match, preserve the document values and report the mismatch in warnings.\n14. Return ONLY valid JSON matching the schema. No markdown, no explanations.\n";

export const EXTRACTION_PROMPT = "Analyze the attached customer purchase order (a PO issued by a customer TO India Glycols Ltd).\n\nConvert it into the standardized Sales Order JSON schema.\n\nField guide (SO Step):\n- customer.*            -> the party that ISSUED the PO (letterhead / their Bill-To block): name, GSTIN, PAN, full address.\n- ship_to.*             -> the delivery/consignee block (name, full address, GSTIN if printed).\n- supplier_on_po.*      -> India Glycols entity as printed (name, GSTIN, address) \u2014 used to identify the supplying plant.\n- sales_order.customer_po_number -> the customer's PO number exactly as printed.\n- sales_order.customer_po_date   -> the PO date as printed.\n- sales_order.payment_term       -> payment terms as printed.\n- sales_order.incoterm / incoterm_location / incoterm2_location -> delivery term and its location(s).\n- sales_order.basis_of_delivery  -> the full printed delivery-basis phrase.\n- sales_order.test_report_required -> \"Yes\" when a COA/test certificate is demanded, \"No\" when explicitly not required, null when silent.\n- sales_order.insurance          -> insurance clause as printed, else null.\n- sales_order.discount_credit_note -> any discount, rate difference or credit-note condition, else null.\n- sales_order.schedule_dispatch_date -> requested dispatch/delivery schedule date(s).\n- sales_order.eta_date           -> required-arrival/ETA date if printed.\n- items[]               -> one entry per product line: the customer's item code (their code), the IGL material/product name (e.g. \"IGSOL 12026 E (GLYCOL ETHER)\", \"DIETHYLENE GLYCOL MONO ETHYL ETHER\"), packaging (\"52 DRUMS X 195 KGS\"), HSN, quantity, unit, rate, per (unit of rate), taxable amount, GST type/%/amount, line total, per-line delivery date.\n- summary.*             -> document totals exactly as printed.\n\nRequirements:\n- Read every page.\n- Preserve line item order.\n- Preserve quantities, prices, taxes, totals, GSTIN, PAN, HSN and material codes exactly.\n- If a field is unavailable return null. Never guess values.\n- Return ONLY valid JSON matching the schema below.\n";

export const SCHEMA = {
 "metadata": {
  "document_type": "Customer Purchase Order",
  "department": "Marketing",
  "document_subtype": "Sales Order Input",
  "source": {
   "filename": "",
   "file_type": "pdf"
  }
 },
 "customer": {
  "name": "",
  "gstin": "",
  "pan": "",
  "address": "",
  "bill_to_name": "",
  "bill_to_gstin": "",
  "bill_to_address": ""
 },
 "ship_to": {
  "name": "",
  "address": "",
  "gstin": ""
 },
 "supplier_on_po": {
  "name": "",
  "gstin": "",
  "address": ""
 },
 "sales_order": {
  "sold_to_party": "",
  "ship_to_party": "",
  "customer_po_number": "",
  "customer_po_date": "",
  "payment_term": "",
  "incoterm": "",
  "incoterm_location": "",
  "incoterm2_location": "",
  "basis_of_delivery": "",
  "plant": null,
  "industry_key": null,
  "test_report_required": "",
  "insurance": "",
  "discount_credit_note": "",
  "schedule_dispatch_date": "",
  "eta_date": "",
  "material_with_packaging": "",
  "total_quantity": null,
  "unit": "",
  "price_summary": ""
 },
 "master_match": {
  "matched": false,
  "method": "",
  "customer_code": "",
  "customer_name": "",
  "gstin": "",
  "address": "",
  "issues": []
 },
 "items": [
  {
   "line_number": "",
   "customer_item_code": "",
   "material_code": "",
   "description": "",
   "packaging_type": "",
   "material_with_packaging": "",
   "hsn_code": "",
   "quantity": 0,
   "unit": "",
   "unit_price": 0,
   "price_per": "",
   "taxable_amount": 0,
   "gst_type": "",
   "gst_percent": 0,
   "gst_amount": 0,
   "total_amount": 0,
   "delivery_date": ""
  }
 ],
 "summary": {
  "subtotal": 0,
  "cgst": 0,
  "sgst": 0,
  "igst": 0,
  "grand_total": 0,
  "amount_in_words": ""
 },
 "remarks": [],
 "additional_information": {},
 "missing_fields": [],
 "validation": {
  "subtotal_matches": true,
  "gst_matches": true,
  "grand_total_matches": true,
  "mandatory_fields_complete": true,
  "line_item_count": 0
 },
 "warnings": [],
 "errors": []
};
