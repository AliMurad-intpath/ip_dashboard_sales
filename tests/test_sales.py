from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestSalesDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rep = new_test_user(cls.env, login='ip_sales_rep', groups='sales_team.group_sale_salesman,ip_dashboard.group_dashboard_own')
        cls.other = new_test_user(cls.env, login='ip_sales_other', groups='sales_team.group_sale_salesman,ip_dashboard.group_dashboard_own')
        cls.reader = new_test_user(cls.env, login='ip_sales_reader', groups='sales_team.group_sale_salesman,ip_dashboard.group_dashboard_readonly')
        cls.customer = cls.env['res.partner'].create({'name':'Sales test customer'})
        cls.product = cls.env['product.product'].create({'name':'Sales test service','type':'service','list_price':100})
        cls.order = cls.env['sale.order'].create({'partner_id':cls.customer.id,'user_id':cls.rep.id,
            'order_line':[Command.create({'product_id':cls.product.id,'product_uom_qty':2,'price_unit':100,'tax_id':[Command.clear()]})]})
        cls.order.action_confirm()
        cls.board=cls.env['ip.dashboard'].with_user(cls.rep).create({'name':'Sales tests','company_id':cls.env.company.id,
            'blocks':[{'id':'sales','source':'sales.bookings','kind':'kpi','width':1,'filters':{'ownership':'mine'}}]})

    def test_live_order_value(self):
        result=self.board.with_user(self.rep).fetch_data({'period':'all'})['results']['sales']
        self.assertNotIn('error',result)
        self.assertAlmostEqual(result['value'],self.order.amount_untaxed)

    def test_own_dashboard_does_not_leak(self):
        with self.assertRaises(AccessError):
            self.board.with_user(self.other).sales_open_orders('sales',{'period':'all'})

    def test_readonly_viewer_keeps_sales_record_rules(self):
        result=self.board.with_user(self.reader).fetch_data({'period':'all'})['results']['sales']
        self.assertNotIn('error',result)
        self.assertEqual(result['value'],0)
        with self.assertRaises(AccessError):
            self.board.with_user(self.reader).write({'name':'Blocked'})

    def test_action_is_scoped_and_unknown_block_rejected(self):
        action=self.board.with_user(self.rep).sales_open_orders('sales',{'period':'all'})
        self.assertIn(('company_id','=',self.env.company.id),action['domain'])
        self.assertIn(('user_id','=',self.rep.id),action['domain'])
        # The web client builds window actions from `views`; without it the action throws in the browser.
        self.assertEqual(action['views'],[(False,'tree'),(False,'form')])
        with self.assertRaises(ValidationError):
            self.board.with_user(self.rep).sales_open_orders('missing',{'period':'all'})

    def test_cross_company_rejected(self):
        company=self.env['res.company'].create({'name':'Other sales company'})
        with self.assertRaises(AccessError):
            self.board.with_user(self.rep).sales_open_orders('sales',{'period':'all'},company.id)

    def test_static_arabic_labels_without_ar_language(self):
        self.board.with_user(self.rep).write({'blocks':[{'id':'age','source':'sales.quote_age','kind':'table','width':2}]})
        result=self.board.with_user(self.rep).fetch_data({'period':'all'},language='ar')['results']['age']
        self.assertNotIn('error',result)
        self.assertEqual(result['rows'][0]['label'],'حتى 7 أيام')

    def test_foreign_pricelist_amount_keeps_order_currency(self):
        currency = self.env['res.currency'].search([('id','!=',self.env.company.currency_id.id)],limit=1)
        if not currency:
            self.skipTest('A second currency is required')
        currency.active = True
        pricelist = self.env['product.pricelist'].create({'name':'Foreign sales test', 'currency_id':currency.id})
        order = self.env['sale.order'].create({'partner_id':self.customer.id,'user_id':self.rep.id,
            'pricelist_id':pricelist.id,
            'order_line':[Command.create({'product_id':self.product.id,'product_uom_qty':1,'price_unit':50,'tax_id':[Command.clear()]})]})
        order.action_confirm()
        result = self.board.with_user(self.rep).fetch_data({'period':'all'})['results']['sales']
        foreign = next(r for r in result['currency_results'] if r['currency_id']==currency.id)
        self.assertEqual(foreign['currency'],currency.name)
        self.assertAlmostEqual(foreign['value'],50)
        action = self.board.with_user(self.rep).sales_open_orders('sales',{'period':'all'},currency_id=currency.id)
        self.assertIn(('currency_id','=',currency.id),action['domain'])

    def test_followup_respects_selected_dates(self):
        self.board.with_user(self.rep).write({'blocks':[{'id':'followup','source':'sales.no_invoice','kind':'kpi','width':1,'filters':{'ownership':'mine'}}]})
        result=self.board.with_user(self.rep).fetch_data({'period':'custom','date_from':'2000-01-01','date_to':'2000-01-31'})['results']['followup']
        self.assertNotIn('error',result)
        self.assertEqual(result['value'],0)
        result=self.board.with_user(self.rep).fetch_data({'period':'all'})['results']['followup']
        self.assertGreaterEqual(result['value'],1)
