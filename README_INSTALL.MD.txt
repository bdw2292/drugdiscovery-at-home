conda create -n pyenv --yes
conda activate pyenv
conda install jupyter notebook --yes
conda install -c conda-forge nglview --yes
conda install -c conda-forge mdtraj --yes
conda install -c conda-forge ipywidgets --yes
conda install -c anaconda ipython --yes
pip install git+https://github.com/hainm/fullscreen
jupyter nbextension install fullscreen --py --sys-prefix
jupyter nbextension enable  fullscreen --py --sys-prefix
pip install pyautogui
conda install -c conda-forge jupyter_contrib_nbextensions --yes
conda install -c conda-forge jupyter_nbextensions_configurator --yes
jupyter contrib nbextension install --user
conda install -c conda-forge tqdm --yes
pip install idle-time
conda install -c conda-forge pynput --yes
conda install -c conda-forge selenium --yes
pip install webdriver-manager
conda install pyqt --yes
