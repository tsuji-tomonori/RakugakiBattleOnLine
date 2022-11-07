FROM public.ecr.aws/lambda/python:3.9

COPY *.py model.h5 label.csv requirements.txt ./

RUN python3.9 -m pip install -r requirements.txt -t . --no-compile

CMD ["lambda_function.lambda_handler"]