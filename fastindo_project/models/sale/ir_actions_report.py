from odoo import models, api
from odoo.tools.pdf import merge_pdf
import base64


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # Check if the report is the sale order report
        if report_ref != 'sale.report_saleorder' and report_ref != 'sale.action_report_saleorder':
            return super()._render_qweb_pdf(report_ref, res_ids, data)

        # Generate the standard PDF
        pdf_content, report_type = super()._render_qweb_pdf(report_ref, res_ids, data)

        if not res_ids or report_type != 'pdf':
            return pdf_content, report_type

        # Use sudo() to ensure we can read product certificates which might have restricted access
        orders = self.env['sale.order'].browse(res_ids)
        
        # Check if any order in the batch needs certificates
        if any(order.include_certificates for order in orders):
            pdf_list = [pdf_content]
            added_certificates = set()  # To avoid attaching the same certificate multiple times
            
            for order in orders:
                if order.include_certificates:
                    # Get all products in the order lines
                    products = order.order_line.mapped('product_id')
                    for product in products:
                        # Use the template certificate if variant doesn't have one (usually on template)
                        cert = product.certificate or product.product_tmpl_id.certificate
                        if cert and cert not in added_certificates:
                            try:
                                cert_data = base64.b64decode(cert)
                                # Basic check if it's a PDF
                                if cert_data.startswith(b'%PDF'):
                                    pdf_list.append(cert_data)
                                    added_certificates.add(cert)
                            except Exception:
                                # Skip invalid certificates
                                continue
            
            if len(pdf_list) > 1:
                # merge_pdf expects a list of bytes
                result = merge_pdf(pdf_list)
                return result, report_type

        return pdf_content, report_type
