"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.

"""
import functools

import click
from constant_sorrow.constants import NO_BLOCKCHAIN_CONNECTION
from twisted.internet import stdio

from nucypher.blockchain.eth.utils import datetime_at_period
from nucypher.characters.banners import URSULA_BANNER
from nucypher.cli import actions, painting
from nucypher.cli.actions import (
    get_nucypher_password,
    select_client_account,
    get_client_password
)
from nucypher.cli.config import nucypher_click_config
from nucypher.cli.processes import UrsulaCommandProtocol
from nucypher.cli.types import (
    EIP55_CHECKSUM_ADDRESS,
    NETWORK_PORT,
    EXISTING_READABLE_FILE
)
from nucypher.config.characters import UrsulaConfiguration
from nucypher.config.keyring import NucypherKeyring
from nucypher.utilities.sandbox.constants import (
    TEMPORARY_DOMAIN,
)


# Args (geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
#       rest_port, db_filepath, poa)
def _admin_options(func):
    @click.option('--geth', '-G', help="Run using the built-in geth node", is_flag=True)
    @click.option('--provider', 'provider_uri', help="Blockchain provider's URI", type=click.STRING)
    @click.option('--network', help="Network Domain Name", type=click.STRING)
    @click.option('--registry-filepath', help="Custom contract registry filepath", type=EXISTING_READABLE_FILE)
    @click.option('--staker-address', help="Run on behalf of a specified staking account", type=EIP55_CHECKSUM_ADDRESS)
    @click.option('--worker-address', help="Run the worker-ursula with a specified address",
                  type=EIP55_CHECKSUM_ADDRESS)
    @click.option('--federated-only', '-F', help="Connect only to federated nodes", is_flag=True, default=None)
    @click.option('--rest-host', help="The host IP address to run Ursula network services on", type=click.STRING)
    @click.option('--rest-port', help="The host port to run Ursula network services on", type=NETWORK_PORT)
    @click.option('--db-filepath', help="The database filepath to connect to", type=click.STRING)
    @click.option('--poa', help="Inject POA middleware", is_flag=True, default=None)
    @click.option('--light', help="Indicate that node is light", is_flag=True, default=False)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


# Args (geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
#       rest_port, db_filepath, poa, config_file, dev, lonely, teacher_uri, min_stake)
def _api_options(func):
    @_admin_options
    @click.option('--config-file', help="Path to configuration file", type=EXISTING_READABLE_FILE)
    @click.option('--dev', '-d', help="Enable development mode", is_flag=True)
    @click.option('--lonely', help="Do not connect to seednodes", is_flag=True)
    @click.option('--teacher', 'teacher_uri', help="An Ursula URI to start learning from (seednode)", type=click.STRING)
    @click.option('--min-stake', help="The minimum stake the teacher must have to be a teacher", type=click.INT,
                  default=0)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@click.group()
def ursula():
    """
    "Ursula the Untrusted" PRE Re-encryption node management commands.
    """

    pass


@ursula.command()
@_admin_options
@click.option('--force', help="Don't ask for confirmation", is_flag=True)
@click.option('--config-root', help="Custom configuration directory", type=click.Path())
@nucypher_click_config
def init(click_config,

         # Admin Options
         geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
         rest_port, db_filepath, poa, light,

         # Other
         force, config_root):
    """
    Create a new Ursula node configuration.
    """

    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=None, force=force)

    ETH_NODE = NO_BLOCKCHAIN_CONNECTION
    if geth:
        ETH_NODE = actions.get_provider_process()
        provider_uri = ETH_NODE.provider_uri(scheme='file')
    #############

    if (not staker_address or not worker_address) and not federated_only:
        if not staker_address:
            prompt = "Select staker account"
            staker_address = select_client_account(emitter=emitter, prompt=prompt, provider_uri=provider_uri)

        if not worker_address:
            prompt = "Select worker account"
            worker_address = select_client_account(emitter=emitter, prompt=prompt, provider_uri=provider_uri)
    if not config_root:  # Flag
        config_root = click_config.config_file  # Envvar
    if not rest_host:
        rest_host = actions.determine_external_ip_address(emitter, force=force)
    ursula_config = UrsulaConfiguration.generate(password=get_nucypher_password(confirm=True),
                                                 config_root=config_root,
                                                 rest_host=rest_host,
                                                 rest_port=rest_port,
                                                 db_filepath=db_filepath,
                                                 domains={network} if network else None,
                                                 federated_only=federated_only,
                                                 checksum_address=staker_address,
                                                 worker_address=worker_address,
                                                 registry_filepath=registry_filepath,
                                                 provider_process=ETH_NODE,
                                                 provider_uri=provider_uri,
                                                 poa=poa,
                                                 light=light)
    painting.paint_new_installation_help(emitter, new_configuration=ursula_config)


@ursula.command()
@_admin_options
@click.option('--config-file', help="Path to configuration file", type=EXISTING_READABLE_FILE)
@click.option('--dev', '-d', help="Enable development mode", is_flag=True)
@click.option('--force', help="Don't ask for confirmation", is_flag=True)
@nucypher_click_config
def destroy(click_config,

            # Admin Options
            geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
            rest_port, db_filepath, poa, light,

            # Other
            config_file, force, dev):
    """
    Delete Ursula node configuration.
    """

    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=force)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    actions.destroy_configuration(emitter, character_config=ursula_config, force=force)


@ursula.command()
@_admin_options
@click.option('--config-file', help="Path to configuration file", type=EXISTING_READABLE_FILE)
@click.option('--dev', '-d', help="Enable development mode", is_flag=True)
@nucypher_click_config
def forget(click_config,

           # Admin Options
           geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
           rest_port, db_filepath, poa, light,

           # Other
           config_file,  dev):
    """
    Forget all known nodes.
    """
    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=None)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    actions.forget(emitter, configuration=ursula_config)


@ursula.command()
@_api_options
@click.option('--interactive', '-I', help="Launch command interface after connecting to seednodes.", is_flag=True,
              default=False)
@click.option('--dry-run', '-x', help="Execute normally without actually starting the node", is_flag=True)
@nucypher_click_config
def run(click_config,

        # API Options
        geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
        rest_port, db_filepath, poa, light, config_file, dev, lonely, teacher_uri, min_stake,

        # Other
        interactive, dry_run):
    """
    Run an "Ursula" node.
    """

    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=None)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    URSULA = _create_ursula(ursula_config, click_config, dev, emitter, lonely, teacher_uri, min_stake)

    # GO!
    try:

        # Ursula Deploy Warnings
        emitter.message(
            f"Starting Ursula on {URSULA.rest_interface}",
            color='green',
            bold=True)

        emitter.message(
            f"Connecting to {','.join(ursula_config.domains)}",
            color='green',
            bold=True)

        emitter.message(
            "Working ~ Keep Ursula Online!",
            color='blue',
            bold=True)

        if interactive:
            stdio.StandardIO(UrsulaCommandProtocol(ursula=URSULA, emitter=emitter))

        if dry_run:
            return  # <-- ABORT - (Last Chance)

        # Run - Step 3
        node_deployer = URSULA.get_deployer()
        node_deployer.addServices()
        node_deployer.catalogServers(node_deployer.hendrix)
        node_deployer.run()  # <--- Blocking Call (Reactor)

    # Handle Crash
    except Exception as e:
        ursula_config.log.critical(str(e))
        emitter.message(
            f"{e.__class__.__name__} {e}",
            color='red',
            bold=True)
        raise  # Crash :-(

    # Graceful Exit
    finally:
        emitter.message("Stopping Ursula", color='green')
        ursula_config.cleanup()
        emitter.message("Ursula Stopped", color='red')


@ursula.command(name='save-metadata')
@_api_options
@nucypher_click_config
def save_metadata(click_config,

                  # API Options
                  geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only,
                  rest_host, rest_port, db_filepath, poa, light, config_file, dev, lonely, teacher_uri, min_stake):
    """
    Manually write node metadata to disk without running.
    """
    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=None)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    URSULA = _create_ursula(ursula_config, click_config, dev, emitter, lonely, teacher_uri, min_stake)

    metadata_path = URSULA.write_node_metadata(node=URSULA)
    emitter.message(f"Successfully saved node metadata to {metadata_path}.", color='green')


@ursula.command()
@_api_options
@nucypher_click_config
def view(click_config,

         # API Options
         geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only, rest_host,
         rest_port, db_filepath, poa, light, config_file, dev, lonely, teacher_uri, min_stake):
    """
    View the Ursula node's configuration.
    """

    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=None)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    URSULA = _create_ursula(ursula_config, click_config, dev, emitter, lonely, teacher_uri, min_stake)

    if not URSULA.federated_only:
        blockchain = URSULA.staking_agent.blockchain

        emitter.echo("BLOCKCHAIN ----------\n")
        painting.paint_contract_status(emitter=emitter, registry=URSULA.registry)
        current_block = blockchain.w3.eth.blockNumber
        emitter.echo(f'Block # {current_block}')
        # TODO: 1231
        emitter.echo(f'NU Balance (staker): {URSULA.token_balance}')
        emitter.echo(f'ETH Balance (worker): {blockchain.client.get_balance(URSULA.worker_address)}')
        emitter.echo(f'Current Gas Price {blockchain.client.gas_price}')

    emitter.echo("CONFIGURATION --------")
    response = UrsulaConfiguration._read_configuration_file(filepath=config_file or ursula_config.config_file_location)
    return emitter.ipc(response=response, request_id=0, duration=0)  # FIXME: what are request_id and duration here?


@ursula.command(name='confirm-activity')
@_api_options
@nucypher_click_config
def confirm_activity(click_config,

                     # API Options
                     geth, provider_uri, network, registry_filepath, staker_address, worker_address, federated_only,
                     rest_host, rest_port, db_filepath, poa, light, config_file, dev, lonely, teacher_uri, min_stake):
    """
    Manually confirm-activity for the current period.
    """

    ### Setup ###
    _validate_args(geth, federated_only, staker_address, registry_filepath)

    emitter = _setup_emitter(click_config, worker_address)

    _pre_launch_warnings(emitter, dev=dev, force=None)

    ursula_config, provider_uri = _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev,
                                                     config_file, staker_address, worker_address, federated_only,
                                                     rest_host, rest_port, db_filepath, poa, light)
    #############

    URSULA = _create_ursula(ursula_config, click_config, dev, emitter, lonely, teacher_uri, min_stake)

    receipt = URSULA.confirm_activity()

    confirmed_period = URSULA.staking_agent.get_current_period() + 1
    date = datetime_at_period(period=confirmed_period,
                              seconds_per_period=URSULA.economics.seconds_per_period)

    # TODO: Double-check dates here
    emitter.echo(f'\nActivity confirmed for period #{confirmed_period} '
                 f'(starting at {date})', bold=True, color='blue')
    painting.paint_receipt_summary(emitter=emitter,
                                   receipt=receipt,
                                   chain_name=URSULA.staking_agent.blockchain.client.chain_name)

    # TODO: Check ActivityConfirmation event (see #1193)


def _setup_emitter(click_config, worker_address):
    # Banner
    emitter = click_config.emitter
    emitter.clear()
    emitter.banner(URSULA_BANNER.format(worker_address or ''))

    return emitter


def _validate_args(geth, federated_only, staker_address, registry_filepath):
    #
    # Validate
    #
    if federated_only:
        # TODO: consider rephrasing in a more universal voice.
        if geth:
            raise click.BadOptionUsage(option_name="--geth",
                                       message="--geth cannot be used in federated mode.")

        if staker_address:
            raise click.BadOptionUsage(option_name='--staker-address',
                                       message="--staker-address cannot be used in federated mode.")

        if registry_filepath:
            raise click.BadOptionUsage(option_name="--registry-filepath",
                                       message=f"--registry-filepath cannot be used in federated mode.")


def _pre_launch_warnings(emitter, dev, force):
    if dev:
        emitter.echo("WARNING: Running in Development mode", color='yellow', verbosity=1)
    if force:
        emitter.echo("WARNING: Force is enabled", color='yellow', verbosity=1)


def _get_ursula_config(emitter, geth, provider_uri, network, registry_filepath, dev, config_file,
                       staker_address, worker_address, federated_only, rest_host, rest_port, db_filepath, poa, light):

    ETH_NODE = NO_BLOCKCHAIN_CONNECTION
    if geth:
        ETH_NODE = actions.get_provider_process()
        provider_uri = ETH_NODE.provider_uri(scheme='file')

    if dev:
        ursula_config = UrsulaConfiguration(dev_mode=True,
                                            domains={TEMPORARY_DOMAIN},
                                            poa=poa,
                                            light=light,
                                            registry_filepath=registry_filepath,
                                            provider_process=ETH_NODE,
                                            provider_uri=provider_uri,
                                            checksum_address=staker_address,
                                            worker_address=worker_address,
                                            federated_only=federated_only,
                                            rest_host=rest_host,
                                            rest_port=rest_port,
                                            db_filepath=db_filepath)
    else:
        try:
            ursula_config = UrsulaConfiguration.from_configuration_file(filepath=config_file,
                                                                        domains={network} if network else None,
                                                                        registry_filepath=registry_filepath,
                                                                        provider_process=ETH_NODE,
                                                                        provider_uri=provider_uri,
                                                                        rest_host=rest_host,
                                                                        rest_port=rest_port,
                                                                        db_filepath=db_filepath,
                                                                        poa=poa,
                                                                        light=light,
                                                                        federated_only=federated_only)
        except FileNotFoundError:
            return actions.handle_missing_configuration_file(character_config_class=UrsulaConfiguration,
                                                             config_file=config_file)
        except NucypherKeyring.AuthenticationFailed as e:
            emitter.echo(str(e), color='red', bold=True)
            # TODO: Exit codes (not only for this, but for other exceptions)
            return click.get_current_context().exit(1)

    return ursula_config, provider_uri


def _create_ursula(ursula_config, click_config, dev, emitter, lonely, teacher_uri, min_stake):
    #
    # Make Ursula
    #

    client_password = None
    if not ursula_config.federated_only:
        if not dev and not click_config.json_ipc:
            client_password = get_client_password(checksum_address=ursula_config.worker_address,
                                                  envvar="NUCYPHER_WORKER_ETH_PASSWORD")

    try:
        URSULA = actions.make_cli_character(character_config=ursula_config,
                                            click_config=click_config,
                                            min_stake=min_stake,
                                            teacher_uri=teacher_uri,
                                            dev=dev,
                                            lonely=lonely,
                                            client_password=client_password)

        return URSULA
    except NucypherKeyring.AuthenticationFailed as e:
        emitter.echo(str(e), color='red', bold=True)
        # TODO: Exit codes (not only for this, but for other exceptions)
        return click.get_current_context().exit(1)
