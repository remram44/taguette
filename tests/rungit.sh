#!/usr/bin/env bash

# From : https://adamstraube.github.io/using-gitlab-runner-locally-with-docker-in-docker-on-windows-10-and-wsl/
# 1. Start containter: `rungit.sh up`
# 2. Run stage:  `rungit.sh job <job>`
# 3. Stop containter: `rungit.sh down`

if [[ $# -eq 0 ]]
then
        echo "Usage: {up|down|job}"
        exit 0
fi

PWD_RESOLVED="$(pwd -P)"

function gitlabLoop() {
        stages=($(echo "$1" | tr ',' '\n'))
        if [ -z "$stages" ]; then
                echo "Please pass job name"
        else
                echo "Running jobs(s): ${stages[*]}"
                for stage in ${stages[*]};
                        do
                                gitlabExec $stage
                        done
        fi
}

function gitlabExec() {
    echo PWD=$PWD_RESOLVED
    echo JOB=$1
    docker exec -w $PWD_RESOLVED -it gitlab-runner gitlab-runner exec docker $1 --docker-privileged --docker-disable-cache --docker-volumes '/var/run/docker.sock:/var/run/docker.sock' --env ROOT_PWD=$PWD_RESOLVED
}

case "$1" in

        ## TO CREATE/START DOCKER CONTAINER FOR GITLAB
        up)
                docker run -d --name gitlab-runner --restart always \
                  -v $PWD_RESOLVED:$PWD_RESOLVED \
                  -v /var/run/docker.sock:/var/run/docker.sock \
                  --workdir $PWD_RESOLVED \
                  -v /srv/gitlab-runner/config:/etc/gitlab-runner \
                  gitlab/gitlab-runner:latest
                docker exec gitlab-runner git config --global --add safe.directory $PWD_RESOLVED
        ;;

        ## TO RUN RUNNER AFTER GITLAB CONTAINER HAS STARTED
        job)
                mkdir -p /tmp/gitlabrunner
                gitlabLoop ${2}
                rm -r /tmp/gitlabrunner
        ;;

        ## TO STOP GITLAB CONTAINER
        down)
                docker stop gitlab-runner
                docker rm gitlab-runner
        ;;
esac