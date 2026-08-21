/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class VendorInvoiceReviewDialog extends Component {
    static template = "ai_vendor_invoice.VendorInvoiceReviewDialog";
    static props = { close: Function, record: Object };

    setup() {
        this.state = useState({ result: this.props.record.data.human_review_result || {} });
    }

    get formattedResult() {
        return JSON.stringify(this.state.result, null, 2);
    }

    async confirm() {
        await this.props.record.model.orm.call(
            "vendor.invoice.import.task",
            "action_confirm_review_and_create_bill",
            [[this.props.record.resId], this.state.result],
        );
        await this.props.record.load();
        this.props.close();
    }
}

registry.category("view_widgets").add("vendor_invoice_review_dialog", {
    component: VendorInvoiceReviewDialog,
});
