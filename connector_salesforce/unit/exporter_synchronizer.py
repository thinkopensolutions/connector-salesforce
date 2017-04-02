# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo.addons.queue_job.job import job
from odoo.addons.connector.unit.synchronizer import Exporter
from ..unit.rest_api_adapter import with_retry_on_expiration

_logger = logging.getLogger(__name__)


class SalesforceExporter(Exporter):
    """Exporter to export an Odoo record to Salesforce.

    Exporting using a Salesforce external id field is supported and
    should  be use only if model is exported only.
    It is done by setting _sf_lookup in adapter to the name of external field.
    Switching from export to import direction is possible when using lookup
    but not the way around. To be able to do this all external fields
    must be field with SF Object Id.
    """

    def __init__(self, connector_env):
        super(SalesforceExporter, self).__init__(connector_env)
        self.salesforce_id = None
        self.binding_id = None
        self.binding = None

    def _after_export(self, binding):
        """ Hook called after the export"""
        return

    def _before_export(self):
        """ Hook called before the export"""
        return

    def _deactivate(self):
        """Implementation of the deactivation
        of an Odoo record on Salesforce
        """
        # external id not supported in delete
        # In Salesforce nothing is deleted it is just a flag
        # And deleted ind continue to exist into recycle bin.
        # Recycle bin lifespan is a Salesforce parameter
        # by default it is 15 days
        assert self.binding.salesforce_id
        if self.backend_adapter.exists(self.salesforce_id):
            self.backend_adapter.delete(self.binding.salesforce_id)

    def _to_deactivate(self):
        """Predicate that decide if an Odoo record
        must be deactivated on Salesforce
        """
        assert self.binding
        model = self.env[self.model._name]
        cols = set(model._fields)
        cols.update(model._inherit_fields)
        if 'active' in cols:
            if not self.binding.active:
                return True
        return False

    def _get_record(self):
        """Return current Odoo record

        :return: an record of Odoo model base on
                 `_model_name` key
        :rtype: :py:class:`odoo.osv.orm.BrowseRecord`
        """
        assert self.binding_id
        return self.model.browse(self.binding_id)

    def _map_data_for_upsert(self, mapper, **kwargs):
        """ Call the convert function of the Mapper

        in order to get converted record by using
        mapper.data or mapper.data_for_create

        :return: mapped dic of data to be used by
                 :py:meth:``models.Model.create``
        :rtype: dict
        """
        data = mapper.values(**kwargs)
        return data

    def _upsert(self, salesforce_id, data):
        """Implementation of upserting a record on
        Salesforce.

        upsert means update or create

        :param salesforce_id: the id of Odoo binding to export
        :type salesforce_id: int or long

        :param data: a dict with key and values to be updated created

        :return: the Salesforce uuid of created or updated record
        """
        sf_id = self.backend_adapter.upsert(salesforce_id, data)
        return sf_id

    def _validate_data(self, data):
        """ Check if the values to export are correct

        :param data: data to validate
        Proactively check before the ``_upsert``
        if some fields are missing or invalid.

        Raise `InvalidDataError`
        """
        # we may want to return an NotImplementedError
        return

    def _export(self, binding, salesforce_id):
        """Export a binding record on Salesforce using REST API
        :param binding: the current binding in Odoo
        :type binding: RecordSet

        :param salesforce_id: Salesforce uuid if available else None/False
        :type salesforce_id: str on None

        """
        record_mapper = self.mapper.map_record(self.binding)
        # optimisation trick to avoid lookup binding
        data = self._map_data_for_upsert(record_mapper,
                                         binding=binding,
                                         backend_record=self.backend_record)
        self._validate_data(data)
        sf_id = self._upsert(salesforce_id, data)
        self.binder.bind(sf_id, binding)

    def run(self, binding_id, force_deactivate=False):
        """Try to export or deactivate a record on Salesforce using REST API
        call required hooks and bind the record

        :param binding: the current binding id in Odoo
        :type binding: int or long

        :param force_deactivate: If set to True it will force deactivate
                                 without calling _to_deactivate
                                 mostly use to save some REST calls

        """
        self.binding_id = binding_id
        self.binding = self._get_record()
        if not self.binding:
            raise NotImplementedError(
                'Deactivation of deleted binding is not supported'
            )
        if force_deactivate or self._to_deactivate():
            self._deactivate()
            return
        self._before_export()
        if self.binding.salesforce_id:
            self.salesforce_id = self.binding.salesforce_id
        else:
            if self.backend_adapter._sf_lookup:
                self.salesforce_id = binding_id
        # calls _after_export
        self._export(self.binding, self.salesforce_id)


class SalesforceBatchExporter(Exporter):

    def before_batch_export(self):
        """Hook called before a batch export"""
        pass

    def after_batch_export(self):
        """Hook called after a batch export"""
        pass

    def get_binding_ids_to_export(self, date=False):
        """Return the binding id to export
        if date is set it will lookup on it to
        determine records to exports

        :param date: Odoo date string to do past lookup
        :type date: str

        :return: list of matching bindind id
        :rtype: list
        """
        if not date:
            return self.env[self._model_name].search(
                []
            )
        else:
            return self.env[self._model_name].search(
                ['|',
                 ('salesforce_sync_date', '<', date),
                 ('salesforce_sync_date', '=', False)]
            )

    def run(self, date=False):
        """Try to export or deactivate multiple records on Salesforce
        using REST API. If date is set it will lookup on it to
        determine records to export_record
        call required hooks and bind the record

        :param date: Odoo date string to do past lookup
        :type date: str
        """
        for binding in self.get_binding_ids_to_export(date):
            self._export_record(binding.id)

    def _export_record(self, binding_id):
        """ Export a record directly or delay the export of the record.
        Method to implement in sub-classes.
        """
        raise NotImplementedError


class SalesforceDelayedBatchSynchronizer(SalesforceBatchExporter):

    def _export_record(self, binding_id):
        "Try to export an Odoo binding on Salesforce using jobs"
        export_record.delay(self,
                            self.model._name,
                            self.backend_record.id,
                            binding_id)


class SalesforceDirectBatchSynchronizer(SalesforceBatchExporter):

    def _export_record(self, binding_id):
        "Try to export an Odoo binding on Salesforce directly"
        export_record(self,
                      self.model._name,
                      self.backend_record.id,
                      binding_id)


@with_retry_on_expiration
def batch_export(session, model_name, backend_id, date=False):
    """Export all candidate Odoo binding records On salesforce for a given
    backend, model and date

    :param model_name: name of the binding model.
                       In our case `connector.salesforce.xxx`
    :type model_name: str

    :param backend_id: id of current backend
    :type backend_id: id or long

    :param date: Odoo date string to do past lookup
    :type date: str
    """

    backend = session.env['connector.salesforce.backend'].browse(
        backend_id
    )
    connector_env = backend.get_connector_environment(model_name)
    exporter = connector_env.get_connector_unit(
        SalesforceDirectBatchSynchronizer
    )
    exporter.run(date=date)


@with_retry_on_expiration
def delayed_batch_export(session, model_name, backend_id, date=False):
    """Export all candidate Odoo binding records on Salesforce for a given
    backend, model and date using jobs

    :param model_name: name of the binding model.
                       In our case `connector.salesforce.xxx`
    :type model_name: str

    :param backend_id: id of current backend
    :type backend_id: id or long

    :param date: Odoo date string to do past lookup
    :type date: str
    """
    backend = session.env['connector.salesforce.backend'].browse(
        backend_id
    )
    connector_env = backend.get_connector_environment(model_name)
    exporter = connector_env.get_connector_unit(
        SalesforceDelayedBatchSynchronizer
    )
    exporter.run(date=date)


@job
def export_record(session, model_name, backend_id, binding_id):
    """Export an Odoo binding record on salesforce for a given
    backend, model

    :param model_name: name of the binding model.
                       In our case `connector.salesforce.xxx`
    :type model_name: str

    :param backend_id: id of current backend
    :type backend_id: id or long

    :param binding_id: the id of the Odoo record to export
    :type binding_id: int or long
    """
    backend = session.env['connector.salesforce.backend'].browse(
        backend_id
    )
    connector_env = backend.get_connector_environment(model_name)
    exporter = connector_env.get_connector_unit(
        SalesforceExporter
    )
    exporter.run(binding_id)


@job
def deactivate_record(session, model_name, backend_id, binding_id):
    """deactivate an Odoo binding record on Salesforce for a given
    backend, model

    :param model_name: name of the binding model.
                       In our case `connector.salesforce.xxx`
    :type model_name: str

    :param backend_id: id of current backend
    :type backend_id: id or long

    :param binding_id: the id of the Odoo record to export
    :type binding_id: int or long
    """
    backend = session.env['connector.salesforce.backend'].browse(
        backend_id
    )
    connector_env = backend.get_connector_environment(model_name)
    exporter = connector_env.get_connector_unit(
        SalesforceExporter
    )
    exporter.run(binding_id, force_deactivate=True)
