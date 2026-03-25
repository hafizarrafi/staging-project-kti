import logging

from odoo import models, api, fields, tools

_logger = logging.getLogger(__name__)


class UomUom(models.Model):
    _inherit = 'uom.uom'

    def _adjust_uom_quantities(self, qty, quant_uom):
        """
        Custom override to allow bypassing base UoM conversion.
        If 'force_uom_propagation' is in context, we keep the original UoM.
        """
        if self.env.context.get('force_uom_propagation'):
            return qty, self
        return super()._adjust_uom_quantities(qty, quant_uom)

    def _get_product_id_from_context(self):
        """Helper to find product_id or template_id from various context keys."""
        val = (
            self.env.context.get('product_id') or
            self.env.context.get('default_product_id') or
            self.env.context.get('product_template_id') or
            self.env.context.get('default_product_template_id')
        )
        if isinstance(val, (list, tuple)) and val:
            return val[0]
        if isinstance(val, int):
            return val
        return False

    def _compute_quantity(self, qty, to_unit, round=True, rounding_method='UP', raise_if_failure=True):
        """
        Override _compute_quantity to be product-aware via context.
        This ensures calculations like the UoM widget conversion info are correct.
        """
        product_id = self._get_product_id_from_context()

        if not product_id or not qty:
            return super()._compute_quantity(qty, to_unit, round, rounding_method, raise_if_failure)

        # Lookup template
        res_model = self.env.context.get('product_model')
        if not res_model:
            res_model = self.env.context.get('active_model') or 'product.product'
            if res_model not in ['product.product', 'product.template']:
                 res_model = 'product.product'

        product = self.env[res_model].browse(product_id).exists()
        if not product:
            other_model = 'product.template' if res_model == 'product.product' else 'product.product'
            product = self.env[other_model].browse(product_id).exists()

        template = product if product and product._name == 'product.template' else (product.product_tmpl_id if product else None)

        if not template:
            return super()._compute_quantity(qty, to_unit, round, rounding_method, raise_if_failure)

        custom_factors = {
            f.uom_id.id: f.conversion_factor
            for f in template.uom_factor_ids
            if f.conversion_factor > 0
        }

        if not custom_factors or (self.id not in custom_factors and to_unit.id not in custom_factors):
            return super()._compute_quantity(qty, to_unit, round, rounding_method, raise_if_failure)

        self.ensure_one()
        if self == to_unit:
            return qty

        from_factor = custom_factors.get(self.id, self.factor)
        to_factor = custom_factors.get(to_unit.id, to_unit.factor) if to_unit else 1.0

        amount = qty * from_factor
        if to_unit:
            amount = amount / to_factor

        if to_unit and round:
            amount = tools.float_round(amount, precision_rounding=to_unit.rounding, rounding_method=rounding_method)

        return amount

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to inject custom conversion factors if product_id is in context.
        This fixes the display in the UoM dropdown widget (many2one_uom).
        """
        res = super().read(fields=fields, load=load)
        product_id = self._get_product_id_from_context()

        if not product_id or not fields or ('factor' not in fields and 'relative_factor' not in fields):
            return res

        res_model = self.env.context.get('product_model') or self.env.context.get('active_model') or 'product.product'
        if res_model not in ['product.product', 'product.template']:
            res_model = 'product.product'

        product = self.env[res_model].browse(product_id).exists()

        if not product:
            other_model = 'product.template' if res_model == 'product.product' else 'product.product'
            product = self.env[other_model].browse(product_id).exists()

        if not product:
            return res

        template = product if product._name == 'product.template' else product.product_tmpl_id
        if not template:
            return res

        custom_factors = {
            f.uom_id.id: f.conversion_factor
            for f in template.uom_factor_ids
            if f.conversion_factor > 0
        }

        if not custom_factors:
            return res

        for vals in res:
            uom_id = vals.get('id')
            if uom_id in custom_factors:
                custom_factor = custom_factors[uom_id]
                if 'factor' in vals:
                    vals['factor'] = custom_factor
                if 'relative_factor' in vals:
                    vals['relative_factor'] = custom_factor

        return res
