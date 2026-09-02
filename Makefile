.PHONY: docker-image test deploy-local

docker-image:
	docker build . --file Dockerfile --tag markusressel/esphome-deployment:latest

test:
	pytest

deploy-local:
	cp -a esphome_deployment/* ../esphome-configs/esphome-deployment/esphome_deployment/
	cd ../esphome-configs/esphome-deployment && poetry install