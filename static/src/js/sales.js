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
    async salesOpenOrders(block) {
        if (this.state.salesOpening || this.state.editing || !this.state.board) return;
        this.state.salesOpening = true;
        try {
            const action = await this.orm.call('ip.dashboard', 'sales_open_orders',
                [[this.state.board.id], block.id, {...this.state.filters}, Number(this.state.company), this.result(block)?.currency_id || false]);
            await this.salesAction.doAction(action);
        } catch (error) {
            // Show the server's reason (company, block, access) when there is one, not a guess.
            const reason = error?.data?.message;
            const fallback = this.state.lang === 'ar' ? 'تعذر فتح الأوامر.' : 'Could not open orders.';
            this.notification.add(reason ? fallback + ' ' + reason : fallback, {type:'warning'});
        } finally {
            this.state.salesOpening = false;
        }
    },
    // Sales KPIs open through the server, which narrows exception reports (e.g. orders without
    // an invoice) to the orders that actually have the exception. Rows use the core drill.
    openRecords(block, index = null) {
        if (index === null && block.source?.startsWith('sales.') && !this.state.editing) {
            this.tipClear?.();
            return this.salesOpenOrders(block);
        }
        return super.openRecords(block, index);
    },
    result(block) {
        const result = super.result(block);
        if (!result?.currency_results) return result;
        return result.currency_results.find(item => item.currency_id === this.state.salesCurrencies[block.id]) || result.currency_results[0];
    },
    salesMonthLabel(block, point, index) {
        if (!this.result(block)?.monthly) return index + 1;
        const match = /^(\d{4})-(\d{2})$/.exec(point.label || '');
        if (!match) return point.label;
        const rows = this.result(block).rows;
        if (rows[0]?.label.slice(0,4) !== rows.at(-1)?.label.slice(0,4)) return match[2] + '/' + match[1].slice(2);
        return new Intl.DateTimeFormat(this.state.lang === 'ar' ? 'ar-IQ' : 'en-US', {month:'short', timeZone:'UTC'}).format(new Date(Date.UTC(Number(match[1]), Number(match[2])-1, 1)));
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
});
