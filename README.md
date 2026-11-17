# IP Dashboard — Sales | المبيعات

Versions: **17.0.1.3.0** and **19.0.1.3.0**. Built against your supplied IP Dashboard core **17.0.1.3.3 / 19.0.1.3.3**. This package adds Sales only; it does not replace your core, Finance, Inventory or Builder.

## Install

1. Choose **17/ip_dashboard_sales** or **19/ip_dashboard_sales** for the matching Odoo version. Copy that `ip_dashboard_sales` directory beside your existing `ip_dashboard` addon. Do not put both versions on the same addons path, and do not nest it inside the core.
2. Commit and push to your Odoo.sh staging branch (or restart your local Odoo service after adding the folder).
3. Update the Apps List in developer mode. Remove the default Apps filter, search **IP Dashboard — Sales**, and install it. Dependencies: existing IP Dashboard and Odoo Sales–Inventory integration (`sale_stock`).
4. Refresh the browser. Open IP Dashboard → New dashboard and choose a Sales template. Existing saved dashboards remain unchanged.
5. Assign the existing IP Dashboard role and appropriate Odoo Sales rights. A dashboard Admin does not bypass Sales record rules. A Read-only dashboard user can filter and open orders permitted by their Sales role, but cannot change the dashboard. The order action disables create/edit/delete controls; actual security remains Odoo ACLs and record rules.
6. Optional: enable Odoo's Margins setting (`sale_margin`) before creating a template to include margin blocks. If enabled later, add the new margin sources to an existing dashboard or create a fresh template. No margin data is fabricated when the feature is absent.

## Three templates

| Template | Management question |
|---|---|
| Sales — CEO overview | How much are we selling, how is it changing, who drives sales, and what needs attention? |
| Sales — Customers and products | Which customers, products, categories, salespeople and teams account for performance? |
| Sales — Quotations and follow-up | Which open quotations need attention, what can be invoiced, and how many newly created orders have been confirmed? |

26 sources are defined; 24 are available without the optional margin feature. Layout, fonts, light/dark theme, Arabic/English switch, right-aligned English labels in Arabic view, currency display, block editing and role rules come from your existing core. Chart types include KPI, table, bar, column, line, area, pie and doughnut where appropriate. Each block can be limited to My sales or all sales the viewer is allowed to read. Monetary and order-count breakdowns support month/customer/salesperson/team.

Each Sales block has **Open matching orders / عرض أوامر هذا التقرير**. It opens the saved block's filtered order set in the native Odoo list, respecting company, period and salesperson scope. This opens the whole block's matching set, not a clicked chart slice. Growth opens the current-period orders; the comparison dates are shown in its subtitle. Product/category blocks open contributing orders, not product records.

## Report definitions

| Source | Report | Meaning |
|---|---|---|
| `sales.bookings` | Confirmed sales / قيمة المبيعات المؤكدة | Untaxed confirmed order value in the selected period; not posted revenue or cash received. |
| `sales.orders` | Confirmed orders / عدد أوامر البيع المؤكدة | Number of confirmed orders dated within the selected period. |
| `sales.aov` | Average order value / متوسط قيمة أمر البيع | Untaxed confirmed sales divided by the number of confirmed orders. |
| `sales.customers` | Buying customers / العملاء المشترون | Distinct commercial customers with confirmed orders during the period. |
| `sales.repeat_share` | Repeat-buyer share (%) / نسبة العملاء متكرري الشراء | Customers with at least two confirmed orders in this period / buying customers. Not lifetime retention. |
| `sales.top5_share` | Top-five customer concentration (%) / حصة أكبر خمسة عملاء | Top five positive customer sales balances / all positive customer sales balances. |
| `sales.growth` | Sales change (%) / نسبة تغير المبيعات | Change versus the immediately preceding period of equal length. Requires a positive comparison value. |
| `sales.margin` | Sales order margin / هامش ربح أوامر البيع | Stored Sales margin in the order’s pricelist currency. Depends on recorded costs; not accounting net profit. |
| `sales.margin_pct` | Sales margin (%) / نسبة هامش ربح المبيعات | Total stored Sales margin / total untaxed confirmed sales; not an average of order percentages. |
| `sales.confirmation_days` | Average days to confirm / متوسط أيام تأكيد الطلب | Elapsed days from record creation to confirmation for orders confirmed in the period. |
| `sales.product_sales` | Sales by product / المبيعات حسب المنتج | Confirmed product-line subtotals after discounts and before tax. Down-payment lines are excluded. |
| `sales.category_sales` | Sales by product category / المبيعات حسب فئة المنتج | Confirmed product-line subtotals by current product category; excludes down payments. |
| `sales.quotes_value` | Open quotation value / قيمة عروض الأسعار المفتوحة | Current draft/sent quotations before tax, including expired ones. Not a probability-weighted forecast. |
| `sales.quotes_count` | Open quotations / عدد عروض الأسعار المفتوحة | Current draft and sent quotations, created in the selected period. |
| `sales.expired_quotes` | Expired open quotations / عروض الأسعار المفتوحة المنتهية | Open quotations with an expiry date before today. Missing expiry dates are not classified as expired. |
| `sales.quote_age` | Open quotation aging / أعمار عروض الأسعار المفتوحة | Current open quotation value by days since creation, not days past expiry. |
| `sales.confirmation_rate` | Created-order confirmation rate (%) / نسبة تأكيد الطلبات المنشأة | Orders created in the selected period that are now confirmed / all orders created then. Not CRM win rate. |
| `sales.cancel_rate` | Created-order cancellation rate (%) / نسبة إلغاء الطلبات المنشأة | Orders created in the selected period that are now cancelled / all orders created then. |
| `sales.to_invoice_orders` | Orders ready to invoice / أوامر بيع جاهزة للفوترة | Current confirmed orders with Odoo invoice status To Invoice. This is a count, not an unpaid amount. |
| `sales.quote_followup` | Quotation follow-up list / قائمة متابعة عروض الأسعار | Oldest open quotations first; up to 100 rows. Values before tax, with each order’s currency. |
| `sales.invoice_followup` | Orders to invoice / قائمة الأوامر المطلوب فوترتها | Oldest confirmed orders currently ready to invoice; displayed value is the full untaxed order value. |

## Dates, values and reconciliation

- **Confirmed sales** are current confirmed order values before tax, selected by `date_order` (confirmation date in standard Odoo). They are not posted accounting revenue, invoices, deliveries, cash receipts or a formal profit-and-loss statement. Orders later cancelled are excluded; there is no historical status snapshot.
- All Sales reports respect the dashboard period. Quotations use creation dates; confirmed-order exceptions and ready-to-invoice reports use confirmation dates. Suggested actions combine those two date rules. Current status is evaluated; selecting past dates does not reconstruct past delivery/invoice states. Expired means `validity_date < today`; today and missing expiry dates are not expired.
- Confirmation/cancellation percentages select records by **creation date** and evaluate their **current state**. The denominator includes open, confirmed and cancelled records, including direct orders. These are order-cohort measures, not CRM opportunity win/loss rates.
- Average confirmation days uses creation-to-order-date elapsed time. It is not the CRM sales cycle and cannot reconstruct earlier edits to dates.
- Sales amounts use the recorded order/pricelist currency (`sale.order.currency_id`), with no exchange conversion or rate lookup. Single-currency blocks display that currency automatically. Mixed-currency blocks offer a currency selector; totals, averages, margins, concentration and growth are calculated separately. Growth includes currencies present only in the comparison period. Follow-up tables label each row's currency. No matching orders means no currency is inferred from the company. Counts remain across all currencies. CSV exports include the displayed currency. Matching-order actions follow the displayed currency. Currency selection is a temporary view choice and is not saved to the dashboard layout.
- Growth compares a bounded selected period with the immediately preceding **equal number of calendar days**. It is not automatically year-on-year or calendar-month-on-month. All-time selection and zero/negative comparison sales show **N/A / غير متاح**. Empty conversion cohorts and margins with a zero sales denominator also show N/A.
- Repeat buyers are customers with two or more orders **within the selected period**, not lifetime retention. Customer grouping consolidates contacts using `commercial_partner_id`; equal display names do not merge unrelated customer records.
- Concentration is the largest five positive customer sales balances divided by all positive customer sales balances. It can be 100% when there are fewer than five customers. Negative customer balances are excluded from that ratio only.
- Stored order margins depend on the costs captured by Odoo Sales. They are not actual inventory valuation/COGS or accounting net profit. Margin percentage is weighted by total sales, not the average of individual percentages.
- Product/category reports exclude section/note and down-payment lines; they use discounted, untaxed line subtotals. Therefore they need not reconcile to order totals containing down-payment adjustments. Categories and commercial-customer relationships reflect their current classification.
- Current To Invoice is a **count** of orders with Odoo's `invoice_status = 'to invoice'`. The follow-up table displays full order value, not the remaining amount to invoice and not an unpaid balance. Collections remain in the Finance addon.
- Charts show up to 12 groups. Monthly charts show the latest 12 calendar months chronologically; months without matching orders show zero. Other groups rank by absolute amount/count. KPI totals cover the entire matching set. Pie/doughnut charts inherit the core's negative-value restriction; use a bar/table for signed data.
- Follow-up tables show the first 100 matching records, oldest first; use Open matching orders for the full paginated list. Amounts in these detail tables are full values with the company's decimal precision.
- **Batched processing:** orders, product lines and growth comparisons are scanned in ACL-aware batches of 1,000 using increasing IDs. There is no 5,000-record rejection. Aggregates retain currency/group/customer totals, and follow-up tables retain only the oldest 100 display rows. All matching records contribute to totals. Database load still depends on volume, record rules and installed customizations; this has not been benchmarked on a live server. Other addons' limits are unchanged.

## Why these reports

Research supports sales trends, average deal/order size, margin and breakdowns by product, customer and salesperson as useful management views. CRM win rates, probability-weighted forecasts and quota attainment require distinct opportunity/target data. They are intentionally not represented by open quotation value or invented targets in this Sales addon.

References consulted 16 November 2026:

- [Odoo 19 reporting](https://www.odoo.com/documentation/19.0/applications/essentials/reporting.html): measures, product categories, salesperson and monthly breakdowns.
- [Odoo 17 reporting](https://www.odoo.com/documentation/17.0/applications/essentials/reporting.html): matching report/grouping approach for version 17.
- [Odoo 19 margins](https://www.odoo.com/documentation/19.0/applications/sales/sales/sales_quotations/margin.html): optional margin configuration and calculation basis.
- [Salesforce Revenue Insights](https://help.salesforce.com/s/articleView?id=revenue_insights_overview.htm&language=en_US&type=5): trend, deal-size and sales-cycle management questions. These inform report selection, not Odoo field definitions.
- Official Odoo source, branches `17.0` and `19.0`: `addons/sale/models/sale_order.py`, `sale_order_line.py`, and `addons/sale_margin/models/sale_order.py`. Confirmed version-specific fields and APIs; Odoo 17 uses tree action views / `tax_id`, while 19 uses list / `tax_ids` in test fixtures.

## Verification and limits

The Odoo plugin was attempted twice for `sale.order` and `sale.report`; both returned an MCP connection/rate-limit error (429). **No live database inspection, installation or financial reconciliation was possible, and no business data was changed.** Structure was verified against official Odoo source and the uploaded module bundles instead.

Completed locally: provider arithmetic/domain/currency/permissions adapter checks; all 26 source execution paths; template schema validation; XML inheritance and OWL compilation against both uploaded core versions with and without the supplied Inventory extension; mounted frontend checks for N/A, Arabic, editing and the order-opening button. These do not replace real Odoo tests.

Packaged `ip_dashboard_sales/tests` contains Odoo integration tests for order values, private dashboard isolation, read-only behavior, company isolation and Arabic labels. Run in staging with `--test-enable --test-tags /ip_dashboard_sales` when installing/upgrading. They were not executed here because no Odoo runtime/database was available.

Portable local checks from this extracted folder:

```bash
ODOO_MAJOR=17 python3 validation/test_sales.py -v
ODOO_MAJOR=19 python3 validation/test_sales.py -v
```

After installation, reconcile Confirmed sales with Odoo Sales Analysis using the same dates, company, states and currency basis. Check a foreign-currency order, expired quote, partially invoiced order, read-only dashboard viewer and salesperson with own-record access. Validate both languages and light/dark views. No changes to the uploaded core or other add-ons are needed.

## ملخص التثبيت والاستخدام

اختر مجلد الإصدار المناسب فقط، وضع `ip_dashboard_sales` بجانب الموديول الأساسي ثم ثبّت **IP Dashboard — Sales**. من لوحة البيانات أنشئ لوحة جديدة واختر أحد قوالب المبيعات الثلاثة. احتفظ بمجلدات الموديولات الحالية كما هي.

البيانات المعروضة تخضع لصلاحيات المستخدم والشركة المختارة. قيمة أوامر البيع ليست إيراداً محاسبياً أو مبالغ محصلة. العروض المفتوحة وقوائم المتابعة تعرض الحالة الحالية، بينما مؤشرات المبيعات تتبع الفترة المختارة. تظهر **غير متاح** إذا تعذر حساب نسبة مقارنة صحيحة. يمكن فتح الأوامر المرتبطة بالتقرير من الزر الموجود داخل كل مربع.

## Update 1.1.0 — Exceptions and suggested actions

Four missing counters were added: confirmed goods orders without customer delivery orders; confirmed orders without customer invoices; goods orders missing both; and Draft-only quotations. The existing To Invoice and open quotation counters remain separate because their definitions differ.

The three templates now avoid duplicate block definitions. CEO Overview focuses on totals, growth and profitability; Customers & Products covers customer concentration and breakdowns; Exceptions & Actions holds operational follow-up. Existing saved dashboards are not rewritten: create new dashboards from these templates for the revised layout, or add the new Sales sources manually.

A delivery exists when a linked picking has a customer destination and is not cancelled, even if still draft or waiting. This includes linked dropship pickings; internal transfers alone do not count. Only positive, non-down-payment goods lines make an order delivery-eligible. Service-only orders are excluded from missing-delivery and missing-both counters. An invoice exists if it is a linked, non-cancelled customer invoice; draft invoices count, credit notes do not. A down-payment invoice counts as an invoice, so partially invoiced orders can still be To Invoice without being No Invoice. Broken order-document links cannot be inferred; reconcile links before creating replacements.

All exception counters show current status for orders confirmed in the selected period; draft quotations use creation dates. No Delivery and No Invoice overlap; No Both is their intersection and must not be added to them. The action table lists each affected order only once, oldest first, with the assigned salesperson and a contextual next step. Draft quotations suggest reviewing and sending; missing deliveries suggest checking routes/warehouse/procurement; missing invoices suggest checking invoiceable quantities or waiting for the required delivery/service milestone. These are recommendations only; no business records or messages are created automatically.

Dependencies now include sale_stock (available in Community), which may install Inventory if absent. Users need the appropriate Sales, Inventory and invoicing read permissions for the combined checks. Restricted linked documents make the affected report unavailable rather than falsely claiming a document is missing. Upgrade the Sales addon on your matching Odoo version and refresh assets. The Sales-specific 5,000-order cutoff has been replaced by batched processing.
