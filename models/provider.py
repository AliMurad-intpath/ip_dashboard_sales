"""Sales management reporting. No privileged queries or writes to business records."""
from datetime import datetime, time, timedelta
import re
from zoneinfo import ZoneInfo
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .metrics import summary, grouped, percentage, growth

LIMIT = 5000
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
 'margin': ('Sales order margin', 'هامش ربح أوامر البيع', 'Stored Sales margin, converted to company currency. Depends on recorded costs; not accounting net profit.', 'هامش الربح المسجل في أوامر البيع بحسب التكاليف المدخلة. لا يمثل صافي الربح المحاسبي.'),
 'margin_pct': ('Sales margin (%)', 'نسبة هامش ربح المبيعات', 'Total stored Sales margin / total untaxed confirmed sales; not an average of order percentages.', 'إجمالي هامش الربح مقسوماً على إجمالي المبيعات قبل الضريبة؛ وليس متوسط نسب ربح الطلبات.'),
 'confirmation_days': ('Average days to confirm', 'متوسط أيام تأكيد الطلب', 'Elapsed days from record creation to confirmation for orders confirmed in the period.', 'متوسط المدة بين إنشاء الطلب وتأكيده للأوامر المؤكدة خلال الفترة. الطلبات المؤكدة فوراً تخفض هذا المتوسط.'),
 'product_sales': ('Sales by product', 'المبيعات حسب المنتج', 'Confirmed product-line subtotals after discounts and before tax. Down-payment lines are excluded.', 'قيمة بنود المنتجات المؤكدة بعد الخصم وقبل الضريبة، مع استبعاد بنود الدفعات المقدمة.'),
 'category_sales': ('Sales by product category', 'المبيعات حسب فئة المنتج', 'Confirmed product-line subtotals by current product category; excludes down payments.', 'المبيعات المؤكدة موزعة حسب التصنيف الحالي للمنتجات، من دون بنود الدفعات المقدمة.'),
 'quotes_value': ('Open quotation value', 'قيمة عروض الأسعار المفتوحة', 'Current draft/sent quotations before tax, including expired ones. Not a probability-weighted forecast.', 'قيمة عروض الأسعار غير المؤكدة حالياً قبل الضريبة، بما فيها المنتهية. ليست توقعاً مرجحاً لاحتمال البيع.'),
 'quotes_count': ('Open quotations', 'عدد عروض الأسعار المفتوحة', 'Current draft and sent quotations, regardless of the dashboard period.', 'عدد عروض الأسعار الحالية التي لم تُؤكد بعد، بغض النظر عن الفترة المختارة.'),
 'expired_quotes': ('Expired open quotations', 'عروض الأسعار المفتوحة المنتهية', 'Open quotations with an expiry date before today. Missing expiry dates are not classified as expired.', 'عروض لم تُؤكد وتجاوزت تاريخ صلاحيتها. العرض الذي لا يحمل تاريخ انتهاء لا يُعد منتهياً هنا.'),
 'quote_age': ('Open quotation aging', 'أعمار عروض الأسعار المفتوحة', 'Current open quotation value by days since creation, not days past expiry.', 'قيمة العروض المفتوحة بحسب الأيام منذ إنشائها، لتحديد العروض التي تحتاج متابعة. ليست مدة التأخر عن الصلاحية.'),
 'confirmation_rate': ('Created-order confirmation rate (%)', 'نسبة تأكيد الطلبات المنشأة', 'Orders created in the selected period that are now confirmed / all orders created then. Not CRM win rate.', 'نسبة الطلبات المنشأة خلال الفترة التي أصبحت مؤكدة الآن، من جميع الطلبات المنشأة خلالها. ليست نسبة الفوز بفرص CRM.'),
 'cancel_rate': ('Created-order cancellation rate (%)', 'نسبة إلغاء الطلبات المنشأة', 'Orders created in the selected period that are now cancelled / all orders created then.', 'نسبة الطلبات المنشأة خلال الفترة التي أصبحت ملغاة الآن، بما فيها عروض الأسعار الملغاة.'),
 'to_invoice_orders': ('Orders ready to invoice', 'أوامر بيع جاهزة للفوترة', 'Current confirmed orders with Odoo invoice status To Invoice. This is a count, not an unpaid amount.', 'عدد الأوامر المؤكدة التي يعرض أودو حالتها للفوترة. لا يمثل قيمة الفواتير غير المسددة.'),
 'quote_followup': ('Quotation follow-up list', 'قائمة متابعة عروض الأسعار', 'Oldest open quotations first; up to 100 rows. Values before tax, in company currency.', 'أقدم العروض المفتوحة أولاً، حتى 100 عرض، مع قيمتها قبل الضريبة بعملة الشركة لتسهيل المتابعة.'),
 'invoice_followup': ('Orders to invoice', 'قائمة الأوامر المطلوب فوترتها', 'Oldest confirmed orders currently ready to invoice; displayed value is the full untaxed order value.', 'أقدم الأوامر الجاهزة للفوترة. القيمة المعروضة هي كامل قيمة أمر البيع قبل الضريبة وليست المبلغ المتبقي للفوترة.'),
}
CURRENT = {'quotes_value','quotes_count','expired_quotes','quote_age','to_invoice_orders','quote_followup','invoice_followup'}
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
            kinds = KINDS if key in GROUPABLE or key in ('product_sales','category_sales') else ['table','bar','column','pie','doughnut'] if key == 'quote_age' else ['table'] if key.endswith('followup') else ['kpi']
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

    def _sales_records(self, domain):
        records = self.env['sale.order'].search(domain, order='create_date,id', limit=LIMIT+1)
        check_read(records)
        return records

    def _sales_convert(self, order, amount, company, cache=None):
        day = fields.Date.to_date(order.date_order)
        currency = order.currency_id
        cache = {} if cache is None else cache
        key = (currency.id, company.id, day)
        if key in cache:
            return amount * cache[key]
        # Avoid Odoo's implicit 1.0 fallback when no historical rate exists.
        if currency != company.currency_id:
            for item in (currency, company.currency_id):
                if not self.env['res.currency.rate'].search_count([
                    ('currency_id','=',item.id),('name','<=',day),
                    '|',('company_id','=',False),('company_id','=',company.id)]):
                    raise ValidationError(_('A currency has no historical rate for the order date.'))
        cache[key] = currency._convert(1.0,company.currency_id,company,day,round=False)
        return amount * cache[key]

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
            if key in ('to_invoice_orders','invoice_followup'):
                domain += [('state','in',['sale','done']),('invoice_status','=','to invoice')]
            else:
                domain += [('state','in',['draft','sent'])]
                if key == 'expired_quotes':
                    domain += [('validity_date','<',today)]
            domain += [('create_date','<=',fields.Datetime.now())]
        elif key in COHORT:
            domain = self._sales_dates(domain,'create_date',start,end)
        else:
            domain += [('state','in',['sale','done'])]
            domain = self._sales_dates(domain,'date_order',start,end)
        return spec,key,domain,start,end,today,base

    def _run_source(self, source_key, block, filters, company):
        result = self._sales_run_source(source_key, block, filters, company)
        if source_key.startswith('sales.') and result.get('scope_ar'):
            result['scope_ar'] = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', lambda m: '\u2066'+m.group(0)+'\u2069', result['scope_ar'])
        return result

    def _sales_run_source(self, source_key, block, filters, company):
        if not source_key.startswith('sales.'):
            return super()._run_source(source_key,block,filters,company)
        # Rebind only this provider; does not change other addon data scopes.
        self = self.with_company(company).with_context(allowed_company_ids=[company.id])
        spec,key,domain,start,end,today,base = self._sales_selection(source_key,block,filters,company)
        arabic = self.env.context.get('ip_sales_language') == 'ar' or (not self.env.context.get('ip_sales_language') and (self.env.lang or '').startswith('ar'))
        orders = self._sales_records(domain)
        if len(orders)>LIMIT:
            return {'error':'query_limit'}
        result = dict(value=0.0,unit='currency' if key in MONEY else 'percent' if key in PERCENT else 'number',
            currency=company.currency_id.name,rows=[],truncated=False,group_label='Group',group_label_ar='المجموعة')
        if key in CURRENT:
            en='Current open workload; period filter does not apply.'
            ar='حالة المتابعة الآن؛ لا تتغير عند اختيار فترة أخرى.'
        elif key in COHORT:
            en='Created %s to %s; evaluated at current status.' % (start or 'inception',end)
            ar='طلبات أُنشئت من %s إلى %s، بحسب حالتها الآن.' % (start or 'البداية',end)
        else:
            en='Confirmed %s to %s. Order-date exchange rates; company currency.' % (start or 'inception',end)
            ar='أوامر مؤكدة من %s إلى %s، بعملة الشركة وبسعر الصرف في تاريخ الطلب.' % (start or 'البداية',end)
        if key in MONEY or key.endswith('followup'):
            en += ' Amounts in ' + company.currency_id.name + '.'
            ar += ' المبالغ بعملة ' + company.currency_id.name + '.'
        result.update(scope=en,scope_ar=ar)
        if key in COHORT:
            target = ('sale','done') if key=='confirmation_rate' else ('cancel',)
            result['value']=percentage(sum(o.state in target for o in orders),len(orders))
            if not orders:
                result.update(value=None,not_applicable=True,scope=en+' No orders in this cohort.',scope_ar=ar+' لا توجد طلبات في هذه الفترة لحساب النسبة.')
            return result
        if key in ('product_sales','category_sales'):
            lines = self.env['sale.order.line'].search([('order_id','in',orders.ids),('display_type','=',False),('is_downpayment','=',False)],limit=LIMIT+1)
            check_read(lines)
            if len(lines)>LIMIT:return {'error':'query_limit'}
            rows=[]
            conversions={}
            for line in lines:
                group=line.product_id if key=='product_sales' else line.product_id.categ_id
                check_read(group)
                rows.append(dict(product=group.id,product_label=group.display_name or '',amount=self._sales_convert(line.order_id,line.price_subtotal,company,conversions)))
            result['value']=sum(r['amount'] for r in rows)
            result['rows'],result['truncated']=grouped(rows,'product')
            result.update(group_label='Product' if key=='product_sales' else 'Category',group_label_ar='المنتج' if key=='product_sales' else 'الفئة')
            return result
        if key.endswith('followup'):
            result['columns']=(['الطلب','العميل','مندوب المبيعات','تاريخ الإنشاء','قيمة الطلب ('+company.currency_id.name+')'] if arabic else ['Order','Customer','Salesperson','Created','Order value ('+company.currency_id.name+')'])
            result['records']=[]
            conversions={}
            for order in orders[:100]:
                check_read(order.partner_id);check_read(order.user_id)
                result['records'].append([order.name,order.partner_id.display_name,order.user_id.display_name or '',
                    fields.Datetime.context_timestamp(self,order.create_date).strftime('%Y-%m-%d'),format(self._sales_convert(order,order.amount_untaxed,company,conversions),',.%df' % company.currency_id.decimal_places)])
            result.update(value=len(orders),truncated=len(orders)>100)
            return result
        rows = self._sales_rows(orders,company,key in ('margin','margin_pct'),key not in ('orders','customers','repeat_share','confirmation_days','quotes_count','expired_quotes','to_invoice_orders'))
        if key=='quote_age':
            amounts=[0.0]*4
            for order,row in zip(orders,rows):
                days=max(0,(today-fields.Datetime.context_timestamp(self,order.create_date).date()).days)
                amounts[0 if days<=7 else 1 if days<=30 else 2 if days<=60 else 3]+=row['amount']
            labels=['0–7 days','8–30 days','31–60 days','Over 60 days'] if not arabic else ['حتى 7 أيام','8–30 يوماً','31–60 يوماً','أكثر من 60 يوماً']
            result.update(value=sum(amounts),rows=[dict(label=k,value=v) for k,v in zip(labels,amounts)],group_label='Age since creation',group_label_ar='المدة منذ الإنشاء')
            return result
        if key=='growth':
            if not start:
                result.update(value=None,not_applicable=True,scope='Choose a bounded period to compare sales.',scope_ar='اختر فترة محددة لحساب تغير المبيعات.')
                return result
            previous_end=start-timedelta(days=1)
            previous_start=start-(end-start+timedelta(days=1))
            previous=self._sales_records(self._sales_dates(base+[('state','in',['sale','done'])],'date_order',previous_start,previous_end))
            if len(previous)>LIMIT:return {'error':'query_limit'}
            conversions={}
            before=sum(self._sales_convert(o,o.amount_untaxed,company,conversions) for o in previous)
            change=growth(sum(r['amount'] for r in rows),before)
            result['value']=change
            result['not_applicable']=change is None
            result.update(scope='Compared with %s to %s. %s' % (previous_start,previous_end,'No positive baseline; percentage unavailable.' if change is None else 'Same number of calendar days.'),
                scope_ar='مقارنة بالفترة من %s إلى %s. %s' % (previous_start,previous_end,'لا توجد قيمة مقارنة موجبة؛ النسبة غير متاحة.' if change is None else 'بنفس عدد الأيام.'))
            return result
        values=summary(rows)
        result['value']=sum(r['amount'] for r in rows) if key=='quotes_value' else len(rows) if key in ('quotes_count','expired_quotes','to_invoice_orders') else values[key]
        if key in GROUPABLE and block['kind']!='kpi':
            dim=block.get('filters',{}).get('group_by','month')
            measure='count' if key in ('orders','quotes_count','expired_quotes','to_invoice_orders') else 'margin' if key=='margin' else 'amount'
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
            ('executive','Sales — CEO overview','المبيعات — نظرة تنفيذية','Sales momentum, customer dependence and work requiring attention.','تابع نمو المبيعات والعملاء الأهم وما يحتاج متابعة.',[
                b('bookings'),b('orders'),b('aov'),b('growth'),b('customers'),b('repeat_share'),b('top5_share'),b('confirmation_days'),
                b('bookings','line',2,'month'),b('bookings','bar',2,'salesperson'),b('bookings','bar',2,'customer'),b('category_sales','doughnut',2),b('margin'),b('margin_pct'),b('quotes_value'),b('to_invoice_orders')]),
            ('performance','Sales — Customers and products','المبيعات — العملاء والمنتجات','Understand who buys, what sells and which teams drive sales.','اعرف من يشتري، وما المنتجات الأكثر مبيعاً، وأداء فرق البيع.',[
                b('bookings'),b('customers'),b('aov'),b('top5_share'),b('bookings','table',2,'customer'),b('product_sales','bar',2),b('category_sales','column',2),b('bookings','bar',2,'team'),b('margin','bar',2,'salesperson'),b('orders','column',2,'month')]),
            ('followup','Sales — Quotations and follow-up','المبيعات — العروض والمتابعة','Current quotations and invoicing workload, with created-order conversion.','العروض التي تحتاج متابعة والأوامر الجاهزة للفوترة، مع نسبة تأكيد الطلبات المنشأة.',[
                b('quotes_value'),b('quotes_count'),b('expired_quotes'),b('to_invoice_orders'),b('confirmation_rate'),b('cancel_rate'),b('confirmation_days',width=2),b('quote_age','column',2),b('quotes_value','bar',2,'salesperson'),b('quote_followup','table',4),b('invoice_followup','table',4)])]
        return super()._get_templates()+[dict(key='sales.'+key,name=en,name_ar=ar,description=desc,description_ar=desc_ar,
            blocks=[block for block in blocks if block['source'] in sources]) for key,en,ar,desc,desc_ar,blocks in templates]
