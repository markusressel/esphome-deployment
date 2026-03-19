.PHONY: docker-image test

docker-image:
	docker build . --file Dockerfile --tag markusressel/esphome-deployment:latest

test:
	pytest