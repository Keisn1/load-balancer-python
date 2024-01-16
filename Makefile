##
# Project Title
#
# @file
# @version 0.1

test:
	docker-compose up -d
	sleep 2
	python -m pytest --disable-warnings || true
	docker-compose down

# end
