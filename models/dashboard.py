from odoo import models, _
from odoo.exceptions import AccessError, ValidationError
from .provider import check_read, EXCEPTIONS


class SalesDashboard(models.Model):
    _inherit = 'ip.dashboard'

    def fetch_data(self, filters, company_id=False, language='en'):
        # Keep static Sales labels Arabic even when ar_001 is not installed in Odoo.
        scoped = self.with_context(ip_sales_language='ar' if language == 'ar' else 'en')
        return super(SalesDashboard, scoped).fetch_data(filters, company_id, language)

    def sales_open_orders(self, block_id, filters, company_id=False, currency_id=False):
        self.ensure_one()
        check_read(self)
        company_id = company_id or self.company_id.id or self.env.company.id
        if type(company_id) is not int or company_id not in self.env.companies.ids:
            raise AccessError(_('Select an active allowed company.'))
        if self.company_id and company_id != self.company_id.id:
            raise AccessError(_('This dashboard belongs to another company.'))
        block = next((b for b in self.blocks or [] if b['id'] == block_id), None)
        if not block or not block['source'].startswith('sales.'):
            raise ValidationError(_('Select a saved Sales block.'))
        company = self.env['res.company'].browse(company_id)
        provider = self.env['ip.dashboard.provider'].with_company(company).with_context(allowed_company_ids=[company.id])
        spec,key,domain,start,end,today,base = provider._sales_selection(block['source'],block,filters,company)
        if currency_id:
            if type(currency_id) is not int or currency_id <= 0:
                raise ValidationError(_('Invalid currency.'))
            domain += [('currency_id','=',currency_id)]
        if key in EXCEPTIONS:
            ids=[]
            for batch in provider._sales_batches('sale.order',domain):
                ids.extend(o.id for o,case in provider._sales_exception_rows(batch,key))
            domain += [('id','in',ids)]
        check_read(provider.env['sale.order'])
        return {'type':'ir.actions.act_window','name':_('Sales report — matching orders'),
                'res_model':'sale.order','view_mode':'tree,form','views':[(False,'tree'),(False,'form')],'domain':domain,'target':'current',
                'context':{'allowed_company_ids':[company.id],'create':False,'edit':False,'delete':False}}
