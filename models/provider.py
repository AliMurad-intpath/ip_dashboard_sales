"""Sales management reporting. No privileged queries or writes to business records."""
from datetime import datetime, time, timedelta
import re
from zoneinfo import ZoneInfo
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .metrics import summary, grouped, monthly, percentage, growth

BATCH_SIZE = 1000
KINDS = ['kpi', 'bar', 'table', 'column', 'line', 'area', 'pie', 'doughnut']
GROUPS = ['sales_team.group_sale_salesman', 'sales_team.group_sale_manager']
# Title, Arabic title, explanation, Arabic explanation.
METRICS = {
 'bookings': ('Confirmed sales', 'قيمة المبيعات المؤكدة', 'Untaxed confirmed order value in the selected period; not posted revenue or cash received.', 'قيمة أوامر البيع المؤكدة خلال الفترة قبل الضريبة. لا تمثل الإيرادات المحاسبية أو النقد المحصل.'),
 'orders': ('Confirmed orders', 'عدد أوامر البيع المؤكدة', 'Number of confirmed orders dated within the selected period.', 'عدد أوامر البيع المؤكدة التي يقع تاريخ تأكيدها ضمن الفترة المختارة.'),
 'aov': ('Average order value', 'متوسط قيمة أمر البيع', 'Untaxed confirmed sales divided by the number of confirmed orders.', 'متوسط قيمة الطلب الواحد: المبيعات المؤكدة قبل الضريبة مقسومة على عدد أوامر البيع.'),
 'customers': ('Buying customers', 'العملاء المشترون', 'Distinct commercial customers with confirmed orders during the period.', 'عدد العملاء الذين لديهم أوامر بيع مؤكدة خلال الفترة، مع جمع جهات الاتصال التابعة لنفس الشركة.'),
 'repeat_share': ('Repeat-buyer share (%)', 'نسبة العملاء متكرري الشراء', 'Customers with at least two confirmed orders in this period / buying customers. Not lifetime retention.', 'نسبة العملاء الذين اشتروا مرتين أو أكثر خلال نفس الفترة. لا تقيس الاحتفاظ بالعملاء عبر السنوات.'),
 'top5_share': ('Top-five customer concentration (%)', 'حصة أكبر خمسة عملاء', 'Top five positive customer sales balances / all positive customer sales balances.', 'حصة أكبر خمسة عملاء من المبيعات ذات الرصيد الموجب، لمعرفة مدى اعتماد النشاط على عدد محدود من العملاء.'),
 'growth': ('Sales change (%)', 'نسبة تغير المبيعات', 'Change versus the immediately preceding period of equal length. Requires a positive comparison value.', 'تغير المبيعات مقارنة بالفترة السابقة مباشرة وبنفس عدد الأيام. لا تُحسب النسبة إن لم تكن مبيعات المقارنة موجبة.'),
 'margin': ('Sales order margin', 'هامش ربح أوامر البيع', 'Stored Sales margin in the order’s pricelist currency. Depends on recorded costs; not accounting net profit.', 'هامش الربح المسجل في أوامر البيع بحسب التكاليف المدخلة. لا يمثل صافي الربح المحاسبي.'),
 'margin_pct': ('Sales margin (%)', 'نسبة هامش ربح المبيعات', 'Total stored Sales margin / total untaxed confirmed sales; not an average of order percentages.', 'إجمالي هامش الربح مقسوماً على إجمالي المبيعات قبل الضريبة؛ وليس متوسط نسب ربح الطلبات.'),
 'confirmation_days': ('Average days to confirm', 'متوسط أيام تأكيد الطلب', 'Elapsed days from record creation to confirmation for orders confirmed in the period.', 'متوسط المدة بين إنشاء الطلب وتأكيده للأوامر المؤكدة خلال الفترة. الطلبات المؤكدة فوراً تخفض هذا المتوسط.'),
 'product_sales': ('Sales by product', 'المبيعات حسب المنتج', 'Confirmed product-line subtotals after discounts and before tax. Down-payment lines are excluded.', 'قيمة بنود المنتجات المؤكدة بعد الخصم وقبل الضريبة، مع استبعاد بنود الدفعات المقدمة.'),
 'category_sales': ('Sales by product category', 'المبيعات حسب فئة المنتج', 'Confirmed product-line subtotals by current product category; excludes down payments.', 'المبيعات المؤكدة موزعة حسب التصنيف الحالي للمنتجات، من دون بنود الدفعات المقدمة.'),
 'quotes_value': ('Open quotation value', 'قيمة عروض الأسعار المفتوحة', 'Current draft/sent quotations before tax, including expired ones. Not a probability-weighted forecast.', 'قيمة عروض الأسعار غير المؤكدة حالياً قبل الضريبة، بما فيها المنتهية. ليست توقعاً مرجحاً لاحتمال البيع.'),
 'quotes_count': ('Open quotations', 'عدد عروض الأسعار المفتوحة', 'Current draft and sent quotations, created in the selected period.', 'عدد عروض الأسعار الحالية التي لم تُؤكد بعد، والتي أُنشئت خلال الفترة المختارة.'),
 'expired_quotes': ('Expired open quotations', 'عروض الأسعار المفتوحة المنتهية', 'Open quotations with an expiry date before today. Missing expiry dates are not classified as expired.', 'عروض لم تُؤكد وتجاوزت تاريخ صلاحيتها. العرض الذي لا يحمل تاريخ انتهاء لا يُعد منتهياً هنا.'),
 'quote_age': ('Open quotation aging', 'أعمار عروض الأسعار المفتوحة', 'Current open quotation value by days since creation, not days past expiry.', 'قيمة العروض المفتوحة بحسب الأيام منذ إنشائها، لتحديد العروض التي تحتاج متابعة. ليست مدة التأخر عن الصلاحية.'),
 'confirmation_rate': ('Created-order confirmation rate (%)', 'نسبة تأكيد الطلبات المنشأة', 'Orders created in the selected period that are now confirmed / all orders created then. Not CRM win rate.', 'نسبة الطلبات المنشأة خلال الفترة التي أصبحت مؤكدة الآن، من جميع الطلبات المنشأة خلالها. ليست نسبة الفوز بفرص CRM.'),
 'cancel_rate': ('Created-order cancellation rate (%)', 'نسبة إلغاء الطلبات المنشأة', 'Orders created in the selected period that are now cancelled / all orders created then.', 'نسبة الطلبات المنشأة خلال الفترة التي أصبحت ملغاة الآن، بما فيها عروض الأسعار الملغاة.'),
 'to_invoice_orders': ('Orders ready to invoice', 'أوامر بيع جاهزة للفوترة', 'Current confirmed orders with Odoo invoice status To Invoice. This is a count, not an unpaid amount.', 'عدد الأوامر المؤكدة التي يعرض أودو حالتها للفوترة. لا يمثل قيمة الفواتير غير المسددة.'),
 'quote_followup': ('Quotation follow-up list', 'قائمة متابعة عروض الأسعار', 'Oldest open quotations first; up to 100 rows. Values before tax, with each order’s currency.', 'أقدم العروض المفتوحة أولاً، حتى 100 عرض، مع قيمتها قبل الضريبة بعملة كل طلب لتسهيل المتابعة.'),
 'invoice_followup': ('Orders to invoice', 'قائمة الأوامر المطلوب فوترتها', 'Oldest confirmed orders currently ready to invoice; displayed value is the full untaxed order value.', 'أقدم الأوامر الجاهزة للفوترة. القيمة المعروضة هي كامل قيمة أمر البيع قبل الضريبة وليست المبلغ المتبقي للفوترة.'),
}
METRICS.update({
 'no_delivery': ('Confirmed orders without delivery orders', 'أوامر مؤكدة بلا أوامر تسليم', 'Confirmed orders with positive goods lines and no non-cancelled customer delivery. Service-only orders are excluded. Includes orders missing both documents.', 'أوامر مؤكدة تحتوي بضائع بكميات موجبة ولا يرتبط بها تسليم للعميل غير ملغى. تُستبعد الخدمات فقط، وتشمل الحالات التي تفتقد الفاتورة أيضاً.'),
 'no_invoice': ('Confirmed orders without invoices', 'أوامر مؤكدة بلا فواتير', 'Confirmed orders with no non-cancelled customer invoice. A draft invoice counts as existing; a credit note does not. Not all these orders are invoiceable yet.', 'أوامر مؤكدة بلا فاتورة عميل غير ملغاة. الفاتورة المسودة تُعد موجودة، والإشعار الدائن لا يُعد فاتورة. قد تتطلب بعض الأوامر التسليم أولاً.'),
 'no_both': ('Confirmed orders without delivery or invoice', 'أوامر مؤكدة بلا تسليم ولا فاتورة', 'Goods orders missing both a customer delivery and a customer invoice. This is the intersection of the two preceding counts, not an additional category.', 'أوامر بضائع مؤكدة تفتقد أمر التسليم والفاتورة معاً. هي جزء مشترك من المؤشرين السابقين؛ لا تجمع الأعداد الثلاثة.'),
 'draft_quotes': ('Draft quotations', 'عروض الأسعار المسودة', 'Only quotations in Draft; sent quotations are excluded. Created in the selected period, evaluated at current status.', 'عروض الأسعار في حالة مسودة فقط، دون العروض المرسلة. تعرض العروض المنشأة خلال الفترة المختارة بحسب حالتها الحالية.'),
 'suggested_actions': ('Sales exceptions and suggested actions', 'حالات المبيعات والإجراءات المقترحة', 'One row per affected order or draft quotation, oldest first, up to 100. Suggestions only: no delivery, invoice or message is created automatically.', 'سطر واحد لكل أمر يحتاج معالجة أو عرض مسودة، الأقدم أولاً وحتى 100 سجل. إجراءات مقترحة فقط؛ لا يُنشأ تسليم أو فاتورة ولا تُرسل رسالة تلقائياً.'),
})
EXCEPTIONS = {'no_delivery','no_invoice','no_both','suggested_actions'}

CURRENT = EXCEPTIONS | {'draft_quotes','quotes_value','quotes_count','expired_quotes','quote_age','to_invoice_orders','quote_followup','invoice_followup'}
COHORT = {'confirmation_rate', 'cancel_rate'}
MONEY = {'bookings','aov','margin','product_sales','category_sales','quotes_value','quote_age'}
PERCENT = {'repeat_share','top5_share','growth','margin_pct','confirmation_rate','cancel_rate'}
GROUPABLE = {'bookings','orders','quotes_value','quotes_count','expired_quotes','to_invoice_orders','margin'}
BREAKDOWN = {'key':'group_by','label':'Breakdown','label_ar':'التجميع حسب',
 'options':[['month','Month','الشهر'],['customer','Customer','العميل'],['salesperson','Salesperson','مندوب المبيعات'],['team','Sales team','فريق المبيعات']],
 'domains':{k:[] for k in ['month','customer','salesperson','team']}}
OWNER = {'key':'ownership','label':'Salesperson scope','label_ar':'نطاق مندوب المبيعات',
 'options':[['all','All permitted salespeople','كل المندوبين المسموح بعرض بياناتهم'],['mine','My sales only','مبيعاتي فقط']],
 'domains':{'all':[], 'mine':[]}}


def check_read(records):
    if hasattr(records, 'check_access'):
        records.check_access('read')
    else:
        records.check_access_rights('read')
        if records:
            records.check_access_rule('read')


class SalesProvider(models.AbstractModel):
    _inherit = 'ip.dashboard.provider'

    @api.model
    def _get_sources(self):
        sources = dict(super()._get_sources())
        margin_available = 'margin' in self.env['sale.order'].fields_get(['margin'])
        for key, (en, ar, desc, desc_ar) in METRICS.items():
            if key in ('margin','margin_pct') and not margin_available:
                continue
            kinds = KINDS if key in GROUPABLE or key in ('product_sales','category_sales') else ['table','bar','column','pie','doughnut'] if key == 'quote_age' else ['table'] if key.endswith('followup') or key=='suggested_actions' else ['kpi']
            sources['sales.'+key] = dict(label=en,label_ar=ar,description=desc,description_ar=desc_ar,
                module='Sales',groups=GROUPS,model='sale.order',company_field='company_id',kinds=kinds,
                filters=[OWNER]+([BREAKDOWN] if key in GROUPABLE else []))
        return sources

    def _sales_dates(self, domain, date_field, start, end):
        tz = ZoneInfo(self.env.user.tz or 'UTC')
        def utc(day):
            return datetime.combine(day,time.min,tzinfo=tz).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        if start:
            domain += [(date_field,'>=',utc(start))]
        domain += [(date_field,'<',utc(end+timedelta(days=1)))]
        return domain

    def _sales_batches(self, model, domain):
        """Keyset pagination: ACL-aware, no offset scans or report record ceiling."""
        last_id = 0
        while True:
            batch = self.env[model].search(list(domain)+[('id','>',last_id)], order='id', limit=BATCH_SIZE)
            check_read(batch)
            if not batch:
                return
            yield batch
            last_id = batch[-1].id

    def _sales_convert(self, order, amount, company, cache=None):
        # Order amounts and sale_margin are already expressed in order currency.
        # Currency cohorts are separated before any monetary aggregation.
        return amount

    def _sales_rows(self, orders, company, include_margin=False, include_amount=True):
        rows = []
        conversions = {}
        for order in orders:
            partner = order.partner_id.commercial_partner_id
            check_read(partner)
            check_read(order.user_id)
            check_read(order.team_id)
            local = fields.Datetime.context_timestamp(self,order.date_order)
            row = dict(amount=self._sales_convert(order,order.amount_untaxed,company,conversions) if include_amount else 0.0,count=1,
                customer=partner.id,customer_label=partner.display_name,
                salesperson=order.user_id.id,salesperson_label=order.user_id.display_name or '',
                team=order.team_id.id,team_label=order.team_id.display_name or '',
                month=local.strftime('%Y-%m'),month_label=local.strftime('%Y-%m'),
                days=max(0.0,(order.date_order-order.create_date).total_seconds()/86400))
            if include_margin:
                row['margin'] = self._sales_convert(order,order.margin,company,conversions)
            rows.append(row)
        return rows

    def _sales_case(self, order, key):
        if order.state == 'draft':
            return 'draft'
        missing_delivery = False
        missing_invoice = False
        if key in ('no_delivery','no_both','suggested_actions'):
            check_read(order.order_line)
            goods = False
            for line in order.order_line:
                check_read(line.product_id)
                if not line.display_type and not line.is_downpayment and line.product_uom_qty > 0 and line.product_id.type != 'service':
                    goods = True
            if goods:
                check_read(order.picking_ids)
                has_delivery = False
                for picking in order.picking_ids:
                    check_read(picking.location_dest_id)
                    if picking.state != 'cancel' and picking.location_dest_id.usage == 'customer':
                        has_delivery = True
                missing_delivery = not has_delivery
        if key in ('no_invoice','no_both','suggested_actions'):
            # Check the whole linked recordset: hidden invoices must not become false "missing" cases.
            check_read(order.invoice_ids)
            missing_invoice = not any(inv.move_type == 'out_invoice' and inv.state != 'cancel' for inv in order.invoice_ids)
        if key=='no_both':
            return 'both' if missing_delivery and missing_invoice else None
        return 'both' if missing_delivery and missing_invoice else 'delivery' if missing_delivery else 'invoice' if missing_invoice else None

    def _sales_exception_rows(self, orders, key):
        return [(order,case) for order in orders if (case := self._sales_case(order,key))]

    def _sales_actions(self, order, case, arabic):
        labels={'draft':('Draft quotation','عرض مسودة'),'delivery':('No delivery order','لا يوجد أمر تسليم'),'invoice':('No customer invoice','لا توجد فاتورة عميل'),'both':('No delivery order or invoice','لا يوجد تسليم ولا فاتورة')}
        delivery=('Check goods routes, warehouse and procurement errors; generate the required transfer through the normal fulfilment flow. Do not mark goods delivered without shipment.', 'راجع مسارات المنتجات والمستودع وأخطاء التوريد، ثم أنشئ التحويل المطلوب من دورة التنفيذ المعتادة. لا تسجل التسليم قبل الشحن الفعلي.')
        invoice=(('Review invoiceable quantities and down payments, then create the customer invoice. Check existing links to avoid duplicates.', 'راجع الكميات القابلة للفوترة والدفعات المقدمة، ثم أنشئ فاتورة العميل بعد التحقق من الروابط لتجنب التكرار.') if order.invoice_status=='to invoice' else ('Check the invoicing policy and delivery/service milestones. Complete the required milestone before invoicing; do not force an invoice.', 'راجع سياسة الفوترة والتسليم أو مراحل إنجاز الخدمة. أكمل الشرط المطلوب قبل الفوترة ولا تنشئ فاتورة دون استحقاق.'))
        draft=('Review customer details, prices, validity and availability; obtain internal approval if required, then send the quotation and agree a follow-up date.', 'راجع بيانات العميل والأسعار والصلاحية والتوفر، واحصل على الموافقة الداخلية عند الحاجة، ثم أرسل العرض وحدد موعد المتابعة.')
        index=1 if arabic else 0
        action=draft[index] if case=='draft' else delivery[index] if case=='delivery' else invoice[index] if case=='invoice' else delivery[index]+' '+invoice[index]
        return labels[case][index],action

    def _sales_selection(self, source_key, block, filters, company):
        spec = self._get_sources().get(source_key)
        if not spec or not self._source_allowed(spec):
            raise AccessError(_('Sales source unavailable.'))
        if block['kind'] not in spec['kinds']:
            raise ValidationError(_('Unsupported sales visualization.'))
        domain = self._get_domain(spec,block.get('filters',{}),filters,company)
        if block.get('filters',{}).get('ownership') == 'mine':
            domain += [('user_id','=',self.env.uid)]
        key = source_key.split('.',1)[1]
        start,end = self._period_bounds(filters)
        today = fields.Date.context_today(self)
        end = end or today
        base = list(domain)
        if key in CURRENT:
            if key in EXCEPTIONS:
                domain += [('state','in',['sale','done','draft'] if key=='suggested_actions' else ['sale','done'])]
            elif key=='draft_quotes':
                domain += [('state','=','draft')]
            elif key in ('to_invoice_orders','invoice_followup'):
                domain += [('state','in',['sale','done']),('invoice_status','=','to invoice')]
            else:
                domain += [('state','in',['draft','sent'])]
                if key == 'expired_quotes':
                    domain += [('validity_date','<',today)]
            if key == 'suggested_actions':
                drafts = self._sales_dates([('state','=','draft')], 'create_date', start, end)
                confirmed = self._sales_dates([('state','in',['sale','done'])], 'date_order', start, end)
                from odoo.osv import expression
                domain = expression.AND([domain, expression.OR([drafts, confirmed])])
            else:
                date_field = 'date_order' if key in EXCEPTIONS or key in ('to_invoice_orders','invoice_followup') else 'create_date'
                domain = self._sales_dates(domain, date_field, start, end)
        elif key in COHORT:
            domain = self._sales_dates(domain,'create_date',start,end)
        else:
            domain += [('state','in',['sale','done'])]
            domain = self._sales_dates(domain,'date_order',start,end)
        return spec,key,domain,start,end,today,base

    def _run_source(self, source_key, block, filters, company):
        result = self._sales_run_source(source_key, block, filters, company)
        for item in [result] + result.get('currency_results', []):
            if source_key.startswith('sales.') and item.get('scope_ar'):
                item['scope_ar'] = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', lambda m: '\u2066'+m.group(0)+'\u2069', item['scope_ar'])
        return result

    def _sales_run_source(self, source_key, block, filters, company):
        if not source_key.startswith('sales.'):
            return super()._run_source(source_key,block,filters,company)
        # Rebind only this provider; does not change other addon data scopes.
        self = self.with_company(company).with_context(allowed_company_ids=[company.id])
        spec,key,domain,start,end,today,base = self._sales_selection(source_key,block,filters,company)
        arabic = self.env.context.get('ip_sales_language') == 'ar' or (not self.env.context.get('ip_sales_language') and (self.env.lang or '').startswith('ar'))
        split = key in MONEY | {'top5_share','margin_pct','growth'}
        buckets = {}
        dim = block.get('filters',{}).get('group_by','month') if key in GROUPABLE and block['kind'] != 'kpi' else None
        def bucket(order=None):
            currency = order.currency_id if split and order else None
            if currency:
                check_read(currency)
            code = currency.id if currency else 0
            if code not in buckets:
                buckets[code] = dict(currency=currency, count=0, target=0, cases=0, sample=[], rows={}, ages=[0.0]*4, before=0.0)
            return buckets[code]
        def add_row(data, row, dimension):
            group = row[dimension] if dimension else 0
            target = data['rows'].setdefault(group, dict(row, amount=0.0, margin=0.0, count=0, days=0.0))
            for name in ('amount','margin','count','days'):
                target[name] += row.get(name,0.0)
        for batch in self._sales_batches('sale.order',domain):
            for order in batch:
                data = bucket(order)
                data['count'] += 1
                if key in EXCEPTIONS:
                    case = self._sales_case(order,key)
                    if case:
                        data['cases'] += 1
                        if key == 'suggested_actions':
                            # Keep only the oldest 100 display rows, never all order records.
                            check_read(order.partner_id);check_read(order.user_id)
                            label, action = self._sales_actions(order,case,arabic)
                            row = [order.name,order.partner_id.display_name,order.user_id.display_name or ('غير معيّن' if arabic else 'Unassigned'),label,action]
                            data['sample'].append((order.create_date,order.id,row))
                    continue
                if key.endswith('followup'):
                    check_read(order.partner_id);check_read(order.user_id);check_read(order.currency_id)
                    row = [order.name,order.partner_id.display_name,order.user_id.display_name or '',fields.Datetime.context_timestamp(self,order.create_date).strftime('%Y-%m-%d'),format(order.amount_untaxed,',.%df' % order.currency_id.decimal_places),order.currency_id.name]
                    data['sample'].append((order.create_date,order.id,row))
                    continue
                if key in COHORT:
                    data['target'] += int(order.state in (('sale','done') if key=='confirmation_rate' else ('cancel',)))
                    continue
                if key in ('draft_quotes','product_sales','category_sales'):
                    continue
                row = self._sales_rows([order],company,key in ('margin','margin_pct'),key not in ('orders','customers','repeat_share','confirmation_days','quotes_count','expired_quotes','to_invoice_orders'))[0]
                if key in CURRENT:
                    month = fields.Datetime.context_timestamp(self,order.create_date if key not in ('to_invoice_orders','invoice_followup') else order.date_order).strftime('%Y-%m')
                    row.update(month=month,month_label=month)
                if key=='quote_age':
                    days=max(0,(today-fields.Datetime.context_timestamp(self,order.create_date).date()).days)
                    data['ages'][0 if days<=7 else 1 if days<=30 else 2 if days<=60 else 3] += row['amount']
                add_row(data,row, 'customer' if key in ('customers','repeat_share','top5_share') else dim)
            if key in ('product_sales','category_sales'):
                for lines in self._sales_batches('sale.order.line',[('order_id','in',batch.ids),('display_type','=',False),('is_downpayment','=',False)]):
                    for line in lines:
                        group = line.product_id if key=='product_sales' else line.product_id.categ_id
                        check_read(group)
                        add_row(bucket(line.order_id),dict(product=group.id,product_label=group.display_name or '',amount=line.price_subtotal),'product')
            for data in buckets.values():
                data['sample'] = sorted(data['sample'],key=lambda item:(item[0],item[1]))[:100]
        if key=='growth' and start:
            previous_end=start-timedelta(days=1)
            previous_start=start-(end-start+timedelta(days=1))
            previous_domain=self._sales_dates(base+[('state','in',['sale','done'])],'date_order',previous_start,previous_end)
            for batch in self._sales_batches('sale.order',previous_domain):
                for order in batch:
                    bucket(order)['before'] += order.amount_untaxed
        if not buckets:
            bucket()
        results=[]
        for data in sorted(buckets.values(),key=lambda b: b['currency'].name if b['currency'] else ''):
            result=self._sales_evaluate(key,block,company,[],[],start,end,today,arabic,data['currency'],data)
            if data['currency']:
                result['currency_id']=data['currency'].id
            # KPIs open the orders behind the number; grouped rows are computed in Python, so no row drill.
            result['drill']=self._ip_drill('sale.order', domain+([('currency_id','=',data['currency'].id)] if data['currency'] else []))
            results.append(result)
        return dict(results[0],currency_results=results) if len(results)>1 else results[0]

    def _sales_evaluate(self, key, block, company, orders, previous, start, end, today, arabic, currency, prepared):
        result = dict(value=0.0,unit='currency' if key in MONEY else 'percent' if key in PERCENT else 'number',
            currency=currency.name if currency else '',rows=[],truncated=False,group_label='Group',group_label_ar='المجموعة')
        if key in CURRENT:
            basis = 'confirmation date' if key in EXCEPTIONS or key in ('to_invoice_orders','invoice_followup') else 'creation date'
            basis_ar = 'تاريخ التأكيد' if basis == 'confirmation date' else 'تاريخ الإنشاء'
            if key == 'suggested_actions':
                basis = 'quotation creation / order confirmation date'
                basis_ar = 'تاريخ إنشاء العرض أو تأكيد الأمر'
            en='Selected %s to %s by %s; current status, not a historical snapshot.' % (start or 'inception',end,basis)
            ar='من %s إلى %s حسب %s؛ تُقيّم الحالة الحالية، وليس الوضع التاريخي في نهاية الفترة.' % (start or 'البداية',end,basis_ar)
        elif key in COHORT:
            en='Created %s to %s; evaluated at current status.' % (start or 'inception',end)
            ar='طلبات أُنشئت من %s إلى %s، بحسب حالتها الآن.' % (start or 'البداية',end)
        else:
            en='Confirmed %s to %s.' % (start or 'inception',end)
            ar='أوامر مؤكدة من %s إلى %s.' % (start or 'البداية',end)
        if currency:
            en += ' Order/pricelist currency: ' + currency.name + '. No currency conversion.'
            ar += ' عملة الطلب وقائمة الأسعار: ' + currency.name + '، دون تحويل عملات.'
        elif key in MONEY:
            en += ' No matching orders; no order currency available.'
            ar += ' لا توجد طلبات مطابقة لتحديد عملتها.'
        result.update(scope=en,scope_ar=ar)
        if key=='draft_quotes':
            result['value']=prepared['count']
            return result
        if key in EXCEPTIONS:
            result['value']=prepared['cases']
            if key=='suggested_actions':
                result['columns']=['الطلب','العميل','المسؤول','الحالة','الإجراء المقترح'] if arabic else ['Order','Customer','Owner','Case','Suggested action']
                result['records']=[item[2] for item in prepared['sample']]
                result['truncated']=prepared['cases']>100
            return result
        if key in COHORT:
            target = ('sale','done') if key=='confirmation_rate' else ('cancel',)
            result['value']=percentage(prepared['target'],prepared['count'])
            if not prepared['count']:
                result.update(value=None,not_applicable=True,scope=en+' No orders in this cohort.',scope_ar=ar+' لا توجد طلبات في هذه الفترة لحساب النسبة.')
            return result
        if key in ('product_sales','category_sales'):
            rows=list(prepared['rows'].values())
            result['value']=sum(r['amount'] for r in rows)
            result['rows'],result['truncated']=grouped(rows,'product')
            result.update(group_label='Product' if key=='product_sales' else 'Category',group_label_ar='المنتج' if key=='product_sales' else 'الفئة')
            return result
        if key.endswith('followup'):
            result['columns']=(['الطلب','العميل','مندوب المبيعات','تاريخ الإنشاء','قيمة الطلب','العملة'] if arabic else ['Order','Customer','Salesperson','Created','Order value','Currency'])
            result['records']=[item[2] for item in prepared['sample']]
            result.update(value=prepared['count'],truncated=prepared['count']>100)
            return result
        rows=list(prepared['rows'].values())
        if key=='quote_age':
            amounts=prepared['ages']
            labels=['0–7 days','8–30 days','31–60 days','Over 60 days'] if not arabic else ['حتى 7 أيام','8–30 يوماً','31–60 يوماً','أكثر من 60 يوماً']
            result.update(value=sum(amounts),rows=[dict(label=k,value=v) for k,v in zip(labels,amounts)],group_label='Age since creation',group_label_ar='المدة منذ الإنشاء')
            return result
        if key=='growth':
            if not start:
                result.update(value=None,not_applicable=True,scope='Choose a bounded period to compare sales.',scope_ar='اختر فترة محددة لحساب تغير المبيعات.')
                return result
            previous_end=start-timedelta(days=1)
            previous_start=start-(end-start+timedelta(days=1))
            conversions={}
            before=prepared['before']
            change=growth(sum(r['amount'] for r in rows),before)
            result['value']=change
            result['not_applicable']=change is None
            result.update(scope='Compared with %s to %s. %s' % (previous_start,previous_end,'No positive baseline; percentage unavailable.' if change is None else 'Same number of calendar days.'),
                scope_ar='مقارنة بالفترة من %s إلى %s. %s' % (previous_start,previous_end,'لا توجد قيمة مقارنة موجبة؛ النسبة غير متاحة.' if change is None else 'بنفس عدد الأيام.'))
            return result
        values=summary(rows)
        result['value']=sum(r['amount'] for r in rows) if key=='quotes_value' else prepared['count'] if key in ('quotes_count','expired_quotes','to_invoice_orders') else values[key]
        if key in GROUPABLE and block['kind']!='kpi':
            dim=block.get('filters',{}).get('group_by','month')
            measure='count' if key in ('orders','quotes_count','expired_quotes','to_invoice_orders') else 'margin' if key=='margin' else 'amount'
            if dim == 'month':
                result['rows'],result['truncated'] = monthly(rows, measure, start, end)
                result['monthly'] = True
                result['scope'] += ' Months without matching orders show zero.'
                result['scope_ar'] += ' تُعرض الأشهر التي لا تحتوي طلبات مطابقة بقيمة صفر.'
                if result['truncated']:
                    result['scope'] += ' Latest 12 calendar months shown.'
                    result['scope_ar'] += ' يُعرض آخر 12 شهراً تقويمياً.'
                    result['truncated'] = False
            else:
                result['rows'],result['truncated']=grouped(rows,dim,measure)
            names={'month':('Order month','شهر الطلب'),'customer':('Customer','العميل'),'salesperson':('Salesperson','مندوب المبيعات'),'team':('Sales team','فريق المبيعات')}
            result.update(group_label=names[dim][0],group_label_ar=names[dim][1])
        if key=='margin_pct' and not values['bookings']:
            result.update(value=None,not_applicable=True,scope=en+' No sales denominator.',scope_ar=ar+' لا توجد قيمة مبيعات لحساب النسبة.')
        return result

    @api.model
    def _get_templates(self):
        sources=self._get_sources()
        def b(key,kind='kpi',width=1,group=None):
            en,ar,_,_=METRICS[key]
            if group:
                names={'month':('by month','حسب الشهر'),'customer':('by customer','حسب العميل'),'salesperson':('by salesperson','حسب مندوب المبيعات'),'team':('by sales team','حسب فريق المبيعات')}
                en += ' — '+names[group][0]
                ar += ' — '+names[group][1]
            return dict(id=key+'_'+kind+'_'+(group or 'total'),source='sales.'+key,kind=kind,width=width,title=en,title_ar=ar,
                filters={'group_by':group} if group else {})
        templates=[
            ('executive','Sales — CEO overview','المبيعات — نظرة تنفيذية','Sales totals, growth and profitability.','المبيعات الإجمالية والنمو والربحية.',[
                b('bookings'),b('orders'),b('aov'),b('growth'),b('margin'),b('margin_pct'),b('confirmation_rate'),b('cancel_rate'),b('bookings','line',4,'month')]),
            ('performance','Sales — Customers and products','المبيعات — العملاء والمنتجات','Customer dependence, products and team performance.','تركيز العملاء وأداء المنتجات وفرق المبيعات.',[
                b('customers'),b('repeat_share'),b('top5_share'),b('confirmation_days'),b('bookings','table',2,'customer'),b('product_sales','bar',2),b('category_sales','column',2),b('bookings','bar',2,'team'),b('margin','bar',4,'salesperson')]),
            ('followup','Sales — Exceptions and actions','المبيعات — الحالات والإجراءات','Missing deliveries and invoices, draft quotations and practical next steps.','أوامر تفتقد التسليم أو الفاتورة، وعروض مسودة، وخطوات واضحة للمتابعة.',[
                b('no_delivery'),b('no_invoice'),b('no_both'),b('draft_quotes'),b('suggested_actions','table',4),
                b('quotes_value'),b('quotes_count'),b('expired_quotes'),b('to_invoice_orders'),b('quote_age','column',4)])]
        return super()._get_templates()+[dict(key='sales.'+key,name=en,name_ar=ar,description=desc,description_ar=desc_ar,
            blocks=[block for block in blocks if block['source'] in sources]) for key,en,ar,desc,desc_ar,blocks in templates]
