/** @odoo-module **/
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { IPDashboard } from '@ip_dashboard/js/dashboard';

patch(IPDashboard.prototype, {
    setup() {
        super.setup(...arguments);
        this.salesAction = useService('action');
        this.state.salesOpening = false;
        this.state.salesCurrencies = {};
    },
    result(block) {
        const result = super.result(block);
        if (!result?.currency_results) return result;
        return result.currency_results.find(item => item.currency_id === this.state.salesCurrencies[block.id]) || result.currency_results[0];
    },
    salesCurrencyOptions(block) {
        return this.state.results[block.id]?.currency_results || [];
    },
    salesCurrencyChange(block, event) {
        this.state.salesCurrencies[block.id] = Number(event.target.value);
    },
    exportCSV() {
        const rows = [[this.t('Block title'),this.t('Value'),this.state.lang === 'ar' ? 'العملة' : 'Currency']];
        for (const block of this.blocks) {
            const result = this.result(block); if (!result || result.error) continue;
            rows.push([this.blockTitle(block),result.value,result.currency || '']);
            if(result.columns) { rows.push(result.columns);rows.push(...result.records); }
            for (const row of result.rows || []) rows.push([row.label || this.t('Unspecified'),row.value,result.currency || '']);
        }
        const cell = v => '"'+String(typeof v === 'string' && /^[=+@\-\t\r]/.test(v) ? "'"+v : v).replaceAll('"','""')+'"';
        const url = URL.createObjectURL(new Blob(['\ufeff'+rows.map(row=>row.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
        const a = document.createElement('a'); a.href=url; a.download='IP-Dashboard.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    },
    async salesOpenOrders(block) {
        if (this.state.salesOpening || this.state.editing || !this.state.board) return;
        this.state.salesOpening = true;
        try {
            const action = await this.orm.call('ip.dashboard', 'sales_open_orders',
                [[this.state.board.id], block.id, {...this.state.filters}, Number(this.state.company), this.result(block)?.currency_id || false]);
            await this.salesAction.doAction(action);
        } catch (error) {
            this.notification.add(this.state.lang === 'ar' ? 'تعذر فتح الأوامر. تحقق من الصلاحيات والفلاتر.' : 'Could not open orders. Check permissions and filters.', {type:'warning'});
        } finally {
            this.state.salesOpening = false;
        }
    },
});
