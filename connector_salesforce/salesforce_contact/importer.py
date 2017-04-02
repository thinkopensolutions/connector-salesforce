# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo.addons.connector.exception import MappingError
from odoo.addons.connector.unit.mapper import mapping, only_create
from ..backend import salesforce_backend
from ..unit.binder import SalesforceBinder
from ..unit.importer_synchronizer import (SalesforceDelayedBatchSynchronizer,
                                          SalesforceDirectBatchSynchronizer,
                                          SalesforceImporter,
                                          import_record)
from ..unit.rest_api_adapter import SalesforceRestAdapter
from ..unit.mapper import AddressMapper
_logger = logging.getLogger(__name__)


@salesforce_backend
class SalesforceContactImporter(SalesforceImporter):
    _model_name = 'connector.salesforce.contact'

    def _before_import(self):
        """Hook called before importing a contact
        Ensure that related account is present
        if not it is imported
        """
        assert self.salesforce_record
        if not self.salesforce_record['AccountId']:
            return
        account_binder = self.unit_for(
            SalesforceBinder,
            model='connector.salesforce.account'
        )
        account = account_binder.to_odoo(
            self.salesforce_record['AccountId']
        )
        if not account:
            import_record(
                self,
                'connector.salesforce.account',
                self.backend_record.id,
                self.salesforce_record['AccountId']
            )


@salesforce_backend
class SalesforceDirectBatchContactImporter(SalesforceDirectBatchSynchronizer):
    _model_name = 'connector.salesforce.contact'


@salesforce_backend
class SalesforceDelayedBatchContactImporter(
        SalesforceDelayedBatchSynchronizer):
    _model_name = 'connector.salesforce.contact'


@salesforce_backend
class SalesforceContactAdapter(SalesforceRestAdapter):
    _model_name = 'connector.salesforce.contact'
    _sf_type = 'Contact'


@salesforce_backend
class SalesforceContactMapper(AddressMapper):
    _model_name = 'connector.salesforce.contact'

    direct = [
        ('MailingStreet', 'street'),
        ('MailingPostalCode', 'zip'),
        ('MailingCity', 'city'),
        ('Fax', 'fax'),
        ('Phone', 'phone'),
        ('AssistantPhone', 'sf_assistant_phone'),
        ('OtherPhone', 'sf_other_phone'),
        ('MobilePhone', 'mobile'),
        ('Title', 'function'),
        ('Email', 'email')
    ]

    @only_create
    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @only_create
    @mapping
    def is_company(self, record):
        return {'is_company': False}

    @only_create
    @mapping
    def name(self, record):
        compound_name = ' '.join((record['LastName'], record['FirstName']))
        return {'name': compound_name}

    @mapping
    def country_id(self, record):
        country_id = self._country_id(record, 'MailingCountryCode')
        return {'country_id': country_id}

    @mapping
    def state_id(self, record):
        state_id = self._state_id(record, 'MailingState', 'MailingCountryCode')
        return {'state_id': state_id}

    @mapping
    def customer(self, record):
        return {'customer': True}

    @mapping
    def active(self, record):
        return {'active': True}

    @mapping
    def title_id(self, record):
        title_id = self._title_id(record, 'Salutation')
        return {'title': title_id}

    @mapping
    def parent_id(self, record):
        parent_binder = self.unit_for(
            SalesforceBinder,
            model='connector.salesforce.account',
        )
        if not record['AccountId']:
            return
        parent = parent_binder.to_odoo(
            record['AccountId']
        )
        if not parent:
            raise MappingError(
                'No Account (parent partner) imported for Contact %s' % record
            )
        return {'parent_id': parent.odoo_id.id}
