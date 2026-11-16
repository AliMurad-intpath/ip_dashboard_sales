/** @odoo-module **/
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { IPDashboard } from '@ip_dashboard/js/dashboard';

patch(IPDashboard.prototype, {
    setup() {
        super.setup(...arguments);
        this.salesAction = useService('action');
        this.state.salesOpening = false;
    },
    async salesOpenOrders(block) {
        if (this.state.salesOpening || this.state.editing || !this.state.board) return;
        this.state.salesOpening = true;
        try {
            const action = await this.orm.call('ip.dashboard', 'sales_open_orders',
                [[this.state.board.id], block.id, {...this.state.filters}, Number(this.state.company)]);
            await this.salesAction.doAction(action);
        } catch (error) {
            this.notification.add(this.state.lang === 'ar' ? 'تعذر فتح الأوامر. تحقق من الصلاحيات والفلاتر.' : 'Could not open orders. Check permissions and filters.', {type:'warning'});
        } finally {
            this.state.salesOpening = false;
        }
    },
});
