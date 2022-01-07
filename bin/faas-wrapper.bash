#!/usr/bin/env bash

main() {
    if [[ "$*" != *"build" && "$*" != *"list"* ]]; then
        local image
        local registry
        image="$(yq e '.functions.coss.image' coss.yaml)"
        registry="${image%%/*}"

        docker login "${registry}"

        local gateway
        local gateway_username
        local gateway_password
        local tls_no_verify=""
        gateway="$(yq e '.provider.gateway' coss.yaml)"
        gateway_username="$(kubectl -n openfaas get secret basic-auth -o jsonpath="{.data.basic-auth-user}" | base64 --decode)"
        gateway_password=$(kubectl -n openfaas get secret basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode)

        if [[ "$*" == *"--tls-no-verify"* ]]; then
            tls_no_verify="--tls-no-verify"
        fi

        echo "${gateway_password}" | faas-cli login -g "${gateway}" -u "${gateway_username}" -s "${tls_no_verify}"
    fi

    rm coss/requirements.txt &>/dev/null || true
    poetry export -f requirements.txt --output coss/requirements.txt --without-hashes
    faas-cli "$@" -f coss.yaml
    rm coss/requirements.txt &>/dev/null || true
}

main "$@"
exit $?
