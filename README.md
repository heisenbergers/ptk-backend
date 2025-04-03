# **Quickstart**
The Docker image has already been pushed to a private Dockerhub repository.
To run the service as a pod in Runpod:
1. Login into RunPod's user console, and navigate to the templates (https://www.runpod.io/console/user/templates)
2. Create a new template using the following parameters (remember to add credentials):
![image](https://github.com/user-attachments/assets/c88cf5f2-5f95-4d5e-9ba2-27316b8e850c)
! When adding credentials, enter the Docker API key into the password section, and leave the username empty !
! Note that saved videos will not be persistent unless allocated to a persistent volume ! - This will be done when designating test videos during the demo.
4. You are now ready to run it as a pod! Go to the deployment page (https://www.runpod.io/console/deploy),
