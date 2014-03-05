# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"
provision_script = <<END_OF_LINE
#!/usr/bin/env bash

APTITUDE_UPDATED=/home/vagrant/.aptitude_updated
if [[ ! -e ${APTITUDE_UPDATED} ]]; then
    aptitude update && touch ${APTITUDE_UPDATED}
fi

aptitude --assume-yes install htop libpq-dev python-dev python-pip
pip install --upgrade pip
hash pip
pip install -r /vagrant/requirements.txt

SUPERVISOR_PID_FILE=/tmp/supervisord.pid
if [[ -e ${SUPERVISOR_PID_FILE} ]]; then
    SUPERVISOR_PID=$(< ${SUPERVISOR_PID_FILE})
    kill -HUP ${SUPERVISOR_PID}
else
    supervisord --configuration=/vagrant/supervisord.conf
fi

END_OF_LINE

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
    config.vm.box = "precise64"
    config.vm.box_url = "http://files.vagrantup.com/precise64.box"
    config.vm.network :forwarded_port, guest: 5000, host: 5000, auto_correct: true
    config.vm.provision :shell, :inline => provision_script
end
