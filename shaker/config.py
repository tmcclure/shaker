import os

"""
Shaker configuration
"""

from jinja2 import Template
import yaml
import shaker.ami
import shaker.log
LOG = shaker.log.getLogger(__name__)

DEFAULTS = {
    # These values will be overridden in profile/default or
    # a user profile, or command-line options.
    'hostname': None,
    'domain': None,
    'sudouser': None,
    'ssh_port': '22',
    'ssh_import': None,
    'timezone': None,
    'assign_dns': False,  # Hmmm ...?
    'ec2_access_key_id': None,
    'ec2_secret_access_key': None,
    'ec2_region': 'us-east-1',
    'ec2_zone': None,
    'ec2_instance_type': 'm1.small',
    'ec2_ami_id': None,
    'ubuntu_release': None,
    'ec2_size': None,
    'ec2_key_name': None,
    'ec2_security_group': 'default',
    'ec2_security_groups': [],
    'ec2_security_group_id': None,
    'ec2_security_group_ids': [],
    'ec2_subnet_id': None,
    'ec2_monitoring_enabled': False,
    'ec2_root_device': '/dev/sda1',
    'ec2_architecture': 'i386',
    'ec2_placement_group': None,
    'salt_master': None,
    'salt_id': None,
    'salt_grains': [],
    'salt_pillar_roots_dir': None,
    'cloud_init_template': None,
    'user_data_template': None,
    'minion_template': None,
    'pre_seed': False,
    'ip_address': None
    }


def get_config_dir(path=None):
    """
    Return the shaker configuration directory.  Create and populate
    it if missing.
    """
    if path:
        config_dir = path
    elif os.environ.get('SHAKER_CONFIG_DIR'):
        config_dir = os.environ['SHAKER_CONFIG_DIR']
    else:
        config_dir = os.path.expanduser("~/.shaker")
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir)
    return config_dir


def get_pki_dir(config_dir):
    pki_dir = os.path.join(config_dir, 'pki')
    if not os.path.isdir(pki_dir):
        os.makedirs(pki_dir)
    return pki_dir


def get_userdata_dir(config_dir):
    userdata_dir = os.path.join(config_dir, 'userdata')
    if not os.path.isdir(userdata_dir):
        os.makedirs(userdata_dir)
    return userdata_dir


def default_profile(config_dir):
    profile_dir = os.path.join(config_dir, 'profile')
    default_profile = os.path.join(profile_dir, 'default')
    if not os.path.isdir(profile_dir):
        os.makedirs(profile_dir)
    if not os.path.isfile(default_profile):
        LOG.info("Default profile not found, creating: {0}".format(default_profile))
        template = Template(DEFAULT_PROFILE)
        with open(default_profile, 'w') as f:
            f.write(template.render(DEFAULTS))
    profile = dict(DEFAULTS)
    profile.update(yaml.load(file(default_profile, 'r')) or {})
    return profile


def create_profile(profile, config_dir, profile_name):
    """
    Generate a profile with config parameters and save to disk

    Parameters not specified in the config will inherit from
    the default profile.
    """
    profile_dir = os.path.join(config_dir, 'profile')
    profile_path = os.path.join(profile_dir, profile_name)
    profile_copy = dict(profile)
    if not os.path.isfile(profile_path):
        msg = "Creating new profile: {0}".format(profile_path)
    else:
        msg = "Overwriting profile: {0}".format(profile_path)
    LOG.info(msg)
    print msg
    with open(profile_path, 'w') as f:
        f.write(yaml.dump(profile_copy, default_flow_style=False))
    return profile_copy


def user_profile(cli, config_dir, profile_name=None):
    """User profile, cli overrides defaults.
    """
    profile = default_profile(config_dir) or {}
    if profile_name:
        profile_dir = os.path.join(config_dir, 'profile')
        profile_path = os.path.join(profile_dir, profile_name)
        default_path = os.path.join(profile_dir, 'default')
        if not os.path.isfile(profile_path):
            import shutil
            shutil.copy2(default_path, profile_path)
            LOG.info("Created profile: {0}".format(profile_path))
        else:
            try:
                profile.update(yaml.load(file(profile_path, 'r')) or {})
            except yaml.scanner.ScannerError, err:
                msg = "Error scanning profile {0}: {1}".format(
                    profile_path, err)
                LOG.error(msg)
    else:
        LOG.info("No profile specified.")
    for k, v in cli.__dict__.items():
        if k in profile and v:
            profile[k] = v
    # If the distro is specified in the command-line, we override
    # the profile ec2_ami_id value.
    if cli.distro:
        ec2_ami_id = shaker.ami.get_ami(profile, cli.distro)
        if ec2_ami_id:
            profile['ec2_ami_id'] = ec2_ami_id
        else:
            msg = "Unable to find AMI for distro: {0}".format(cli.distro)
            LOG.info(msg)
    if not profile['ec2_ami_id'] and profile['ubuntu_release']:
        profile['ec2_ami_id'] = shaker.ami.get_ami(profile, profile['ubuntu_release'])
    msg = "Selected AMI {0} in zone {1}".format(
        profile['ec2_ami_id'],
        profile['ec2_zone'])
    LOG.info(msg)

    # if grains are specified in command-line, we override the
    # profile grains value
    if cli.salt_grains:
        grains = {}
        for pair in cli.salt_grains.split(';'):
            for key, value in pair.split(':'):
                grains[key] = value.split(',')
        profile['salt_grains'] = grains

    ## override profile pillar_roots_dir by cli
    if cli.salt_pillar_roots_dir:
        profile['salt_pillar_roots_dir'] = cli.salt_pillar_roots_dir
    return profile


DEFAULT_PROFILE = """####################################################################
# hostname, domain to assign the instance.
####################################################################

#hostname:
#domain:

####################################################################
# salt_master is the location (dns or ip) of the salt master
# to connect to, e.g.: master.example.com
####################################################################

#salt_master:

####################################################################
# salt_id identifies this salt minion.  If not specified,
# defaults to the fully qualified hostname.
####################################################################

#salt_id:

####################################################################
# salt_grains identifies grains on this salt minion.
# If not specified, defaults to empty list.
####################################################################

#salt_grains:

####################################################################
# salt_pillar_roots_dir identifies pillar_roots config on this
# salt minion.
# If not specified, defaults to none and pillar_roots aren't set.
####################################################################

#salt_pillar_roots_dir: /srv/pillar

# Pre-seed the master with a generated salt key, which is copied
# to the minion upon instance creation.  Default is false.
####################################################################

#pre_seed: False

####################################################################
# Assign elastic ip address to minion after the instance is
# launched.  If the ip address is already in use, the
# assignment will fail.  Default is None.
####################################################################

#ip_address:

####################################################################
# Install the user with sudo privileges.  If sudouser is listed
# in ssh_import, the public key will be installed from
# lauchpad.net.  From the command-line, sudouser will default
# to $LOGNAME, if not otherwise specified.
####################################################################

#sudouser:

####################################################################
# Import public keys from lauchpad.net.  Only applicable for
# Ubuntu cloud-init.  User names are comma-separated, no spaces.
####################################################################

#ssh_import:

####################################################################
# ssh_port: You may define a non-standard ssh port, but verify
# it's open in your ec2_security_group.
####################################################################

#ssh_port: {{ ssh_port }}

####################################################################
# timezone:
# e.g. timezone: America/Chicago
# http://en.wikipedia.org/wiki/List_of_tz_database_time_zones
####################################################################

#timezone:

####################################################################
# aws credentials:
# you can set up your aws credentials for this profile
# or you can leave it out and fallback to boto's defaults
# http://docs.pythonboto.org/en/latest/boto_config_tut.html
####################################################################

#ec2_access_key_id: <AWS_ACCESS_KEY_ID>
#ec2_secret_access_key: <AWS_SECRET_ACCESS_KEY>

####################################################################
# ec2_region: EC2 region - us-east-1 (default), eu-west-1, etc.
# ec2_zone: if not specified, EC2 chooses a zone for you
# ec2_placement_group: placement group of an instance with HPC
####################################################################

#ec2_region: {{ ec2_region }}
#ec2_zone: {{ ec2_zone }}
#ec2_placement_group: {{ ec2_placement_group }}
#ec2_subnet_id: {{ ec2_subnet_id }}

####################################################################
# ec2_instance_type defaults to m1.small
# http://aws.amazon.com/ec2/instance-types/
#
# t1.micro
# m1.small  (default)
# m2.xlarge, m2.2xlarge, m2.4xlarge
# c1.medium, c1.xlarge, cc1.4xlarge, cc2.8xlarge
#
####################################################################

#ec2_instance_type: {{ ec2_instance_type }}

####################################################################
# ec2_ami_id: AMI image to launch.  Note AMI's are
# region-specific, so you must specify the the appropriate AMI
# for the ec2_zone above.  ec2_ami_id overrides ubuntu_release
# below.
####################################################################

#ec2_ami_id:

####################################################################
# ubuntu_release: precise, oneiric, natty, maverick, lucid, hardy
# TODO: add support for Debian: sid, etc.
####################################################################

#ubuntu_release: {{ ubuntu_release }}

####################################################################
# ec2_size: size of the root file partition in GB.  If not
# specified (or zero), defaults to the instance type.
####################################################################

#ec2_size: {{ ec2_size }}

####################################################################
# ec2_key_name: Name of the key pair used to create the instance.
# If not specified and only one key-pair is available, it will be
# used.  Otherwise you must specify the key-pair.  Further info:
# http://docs.amazonwebservices.com/AWSEC2/latest/UserGuide/generating-a-keypair.html
####################################################################

#ec2_key_name:

####################################################################
# ec2_security_group: The security group to control port access
# to the instance (ssh, http, etc.)  If not specified, use
# 'default', which generally permits port 22 for ssh access.
####################################################################

#ec2_security_group: default

####################################################################
# ec2_security_groups: Overrides ec2_security_group setting if
# multiple groups are needed.
####################################################################

#ec2_security_groups: []

####################################################################
# ec2_security_group_id: The security group to control port access
# to the instance (ssh, http, etc.)  When specifying subnet_id,
# use this setting instead of ec2_security_group
####################################################################

#ec2_security_group_id: default

####################################################################
# ec2_security_group_ids: Overrides ec2_security_group_id setting
# if multiple groups are needed.
####################################################################

#ec2_security_group_ids: []

####################################################################
# ec2_monitoring_enabled:
# http://aws.amazon.com/cloudwatch/
####################################################################

#ec2_monitoring_enabled: false

####################################################################
# ec2_root_device: root device will be deleted upon termination
# of the instance by default.
####################################################################

#ec2_root_device: /dev/sda1
"""
