FROM public.ecr.aws/lambda/python:3.9

COPY *.py model/model.h5 model/label.csv requirements.txt ./

RUN python3.9 -m pip install -r requirements.txt -t . --no-compile

CMD ["lambda_function.lambda_handler"]