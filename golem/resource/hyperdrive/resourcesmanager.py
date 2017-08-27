import logging
import os
import uuid

from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.base.resourcesmanager import AbstractResourceManager, ResourceBundle
from golem.resource.client import ClientHandler, ClientConfig, ClientCommands

logger = logging.getLogger(__name__)


class HyperdriveResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, daemon_pub_addresses=None,
                 config=None, **kwargs):

        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, **kwargs)

        self._peers = [daemon_pub_addresses]

    def new_client(self):
        return HyperdriveClient(**self.config.client)

    def build_client_options(self, node_id, known_peers=None, **kwargs):
        peers = list(self._peers)
        if known_peers:
            peers += known_peers
        return HyperdriveClient.build_options(node_id, peers=peers, **kwargs)

    def to_wire(self, resources):
        iterator = filter(None, resources)
        return list([r.hash, r.files_split] for r in iterator)

    def from_wire(self, resources):
        iterator = filter(lambda x: x and len(x) > 1, resources)
        return list([r[0], [os.path.join(*x) for x in r[1]]] for r in iterator)

    def add_files(self, files, task_id,
                  absolute_path=False, client=None, client_options=None):

        if not files:
            logger.warning("Resource manager: trying to add an empty file "
                           "collection for task {}".format(task_id))
            return

        files = {path: self.storage.relative_path(path, task_id)
                 for path in files}

        return self._add_files(files, task_id,
                               client=client,
                               client_options=client_options)

    def add_file(self, path, task_id,
                 absolute_path=False, client=None, client_options=None):

        files = {path: os.path.basename(path)}

        return self._add_files(files, task_id,
                               client=client,
                               client_options=client_options)

    def _add_files(self, files, task_id,
                   client=None, client_options=None):

        for f in files.keys():
            if not os.path.exists(f):
                logger.error("Resource manager: file '{}' does not exist"
                             .format(f))
                return

        client = client or self.new_client()
        response = self._handle_retries(client.add,
                                        self.commands.add,
                                        files,
                                        id=task_id,
                                        client_options=client_options,
                                        obj_id=str(uuid.uuid4()))

        self._cache_response(list(files.values()), response, task_id)

    def wrap_file(self, resource):
        resource_path, resource_hash = resource
        return resource_hash, [resource_path]

    def _wrap_resource(self, resource, task_id=None):
        resource_hash, files = resource
        path = self.storage.get_path('', task_id)
        return ResourceBundle(files, resource_hash,
                              task_id=task_id, path=path)

    def _cache_response(self, resources, resource_hash, task_id):
        res = self._wrap_resource((resource_hash, resources), task_id)
        self._cache_resource(res)
