import os

from nucypher.blockchain.eth.constants import DISPATCHER_SECRET_LENGTH, M
from nucypher.config.constants import DEFAULT_CONFIG_ROOT

TEST_KNOWN_URSULAS_CACHE = {}

TEST_URSULA_STARTING_PORT = 7468

DEFAULT_NUMBER_OF_URSULAS_IN_DEVELOPMENT_NETWORK = 10

DEVELOPMENT_TOKEN_AIRDROP_AMOUNT = 1000000 * int(M)

DEVELOPMENT_ETH_AIRDROP_AMOUNT = 10 ** 6 * 10 ** 18  # wei -> ether

MINERS_ESCROW_DEPLOYMENT_SECRET = os.urandom(DISPATCHER_SECRET_LENGTH)

POLICY_MANAGER_DEPLOYMENT_SECRET = os.urandom(DISPATCHER_SECRET_LENGTH)

TEST_URSULA_INSECURE_DEVELOPMENT_PASSWORD = 'this-is-not-a-secure-password'

DEFAULT_SIMULATION_REGISTRY_FILEPATH = os.path.join(DEFAULT_CONFIG_ROOT, 'simulated_registry.json')