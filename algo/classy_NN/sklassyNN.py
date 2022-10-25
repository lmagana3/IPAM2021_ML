"""
Sklearn implementation of classNN.py
"""

import os, sys, csv, types, dill, time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy import stats
from scipy.special import logit, expit
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor

#TODO: 1) see if we can get rid of dill 
#      2) nfeatures no longer needed in input (no build+compilation in sklearn),
#         get rid of it 

#######################################################################
# Default values used in the classes RegressionNN and CrossValidator
#######################################################################
EPOCHS           = 25
BATCH_SIZE       = 64
HLAYERS_SIZES    = (100,)
LEARNING_RATE    = 0.001
VALIDATION_SPLIT = 0.
SEED             = None

#######################################################################
# Usual I/O functions by Marina
#######################################################################
def extract_data(filename, verbose=False, skip_header=False):
    """ Reads data from csv file and returns it in array form.
    """
    lst=[]
    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            lst.append(row)
    if skip_header:
        lst = lst[1:]
    data=np.array(lst, dtype=float)
    if verbose:
        print(filename, 'loaded')
    return data

def write_result(filename, data, verbose=False):
    """ Writes data predicted by trained algorithm into a csv file.
    """
    with open(filename, 'w') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=',')
        for row in data:
            spamwriter.writerow(row)
    if verbose:
        print(filename, 'saved')
    
#######################################################################
# Save/load dictionary that eventually contains lambda-objects
#######################################################################
def save_dill(fname, mydict, verbose=False):
    out_dict_dir = ''
    dict_name = out_dict_dir+fname
    dill.dump(mydict, open(dict_name, 'wb'))
    if verbose:
        print(dict_name, 'saved') 
    return 

def load_dill(fname, verbose=False):
    out_dict_dir = ''
    dict_name = out_dict_dir+fname
    if os.path.exists(dict_name):
        loaded_dict = dill.load(open(dict_name, 'rb'))
        if verbose:
            print(dict_name, 'loaded')
    else:
        loaded_dict = {}
        if verbose:
            print(dict_name, 'not found, returning empty dictionary')
    return loaded_dict    

#######################################################################
# Scaler
#######################################################################
class Scaler:
    """ Compact scaler 
    """
    def __init__(self, A, B, std_scaler=None):
        self.A = A
        self.B = B 
        self.C = self.A*0 # broadcast to correct dimension
        self.D = self.A*0 + 1
        self.std_scaler = std_scaler

    def transform(self,x):
        A = self.A
        B = self.B
        C = self.C
        D = self.D
        x = self.__lin_transf(A,B,C,D,x)
        x = logit(x)
        if self.std_scaler is None:
            std_scaler = StandardScaler()
            std_scaler.fit(x)
            self.std_scaler = std_scaler
        y = self.std_scaler.transform(x)
        return y

    def inverse_transform(self,x):
        A = self.A
        B = self.B
        C = self.C
        D = self.D
        y = self.std_scaler.inverse_transform(x)
        y = expit(y)
        y = self.__lin_transf(C,D,A,B,y)
        return y
    
    def __lin_transf(self,A,B,C,D,x):
        return np.transpose((D-C)*(np.transpose(x)-A)/(B-A)+C)

    def print_info(self):
        for i in range(0,len(self.A)): 
            print('----------------------')
            print('Feature n.', i, sep='')
            print('A        : ', self.A[i])
            print('B        : ', self.B[i])
        return

    def return_dict(self):
        scaler_dict = {}
        scaler_dict['A']          = self.A
        scaler_dict['B']          = self.B
        scaler_dict['std_scaler'] = self.std_scaler
        return scaler_dict 

#######################################################################
# Class for the Regression Neural Newtork
#######################################################################
class RegressionNN:
    """ Class to do regression using a sklearn-NN.
    If model2load='cool_model', load the model and the scalers saved in cool_model/ by save_model(),
    otherwise build a new model according to nfeatures and hlayers_sizes.
    The scalers will be defined when loading the train dataset.
    """
    def __init__(self,hlayers_sizes=HLAYERS_SIZES, model2load=None, verbose=False, seed=SEED):
        # input
        self.hlayers_sizes     = hlayers_sizes
        self.nlayers           = len(hlayers_sizes)
        self.function          = 'MSE' # not used, just a memo
        self.hidden_activation = 'relu'
        
        if seed is None:
            seed = np.random.randint(1,10000)
        self.seed = seed
        if model2load is not None:
            self.__load_model(model2load, verbose=verbose)

    def __check_attributes(self, attr_list):
        """ Check that all the attributes in the list are defined.
        Not essential, but can be useful to check that the functions
        are called in the correct order 
        """
        for i in range(0, len(attr_list)):
            attr = attr_list[i]
            if not hasattr(self, attr):
                if attr=='fit_output':
                    raise ValueError ('Error: '+attr+' is not defined, no model fitting has been performed in this istance')
                else:
                    raise ValueError ('Error: '+attr+' is not defined')
        return
    
    #-----------------------------------------------------------------------------------
    # Load training and test dataset. When loading the training dataset, the scalers 
    # are defined
    #-----------------------------------------------------------------------------------
    def load_train_dataset(self, fname_xtrain='xtrain.csv', fname_ytrain='ytrain.csv', xtrain_data=None, ytrain_data=None, 
                           verbose=False, compact_bounds=None):
        """ Load training dataset and define scalers.
        
        """
        if hasattr(self, 'scaler_x'):
            raise RuntimeError('scaler_x is already defined, i.e. the train dataset has been already loaded.')
        
        # Load training dataset
        if xtrain_data is None:
            xtrain_notnormalized = extract_data(fname_xtrain, verbose=verbose)
        else:
            xtrain_notnormalized = xtrain_data
        if ytrain_data is None:
            ytrain_notnormalized = extract_data(fname_ytrain, verbose=verbose)
        else:
            ytrain_notnormalized = ytrain_data

        nfeatures =len(xtrain_notnormalized[0,:]) 
        self.nfeatures = nfeatures

        # create scalers according to loaded data
        Ax = np.array(compact_bounds['A']).reshape(nfeatures,1)
        Bx = np.array(compact_bounds['B']).reshape(nfeatures,1)
        Ay = Ax
        By = Bx
        ones = np.ones(np.shape(Ax))
        self.scaler_x = Scaler(Ax, Bx)
        self.scaler_y = Scaler(Ay, By)
        xtrain              = self.scaler_x.transform(xtrain_notnormalized)
        ytrain              = self.scaler_y.transform(ytrain_notnormalized)
        self.xtrain         = xtrain
        self.ytrain         = ytrain
        self.ntrain         = len(xtrain[:,0])
        self.xtrain_notnorm = xtrain_notnormalized
        self.ytrain_notnorm = ytrain_notnormalized
        return
        
    def load_test_dataset(self, fname_xtest='xtest.csv', fname_ytest='ytest.csv', xtest_data=None, ytest_data=None, verbose=False):
        self.__check_attributes(['scaler_x', 'scaler_y'])
        if xtest_data is None:
            xtest_notnormalized = extract_data(fname_xtest, verbose=verbose)
        else:
            xtest_notnormalized = xtest_data
        if ytest_data is None:
            ytest_notnormalized = extract_data(fname_ytest, verbose=verbose)
        else:
            ytest_notnormalized = ytest_data
        xtest               = self.scaler_x.transform(xtest_notnormalized)
        ytest               = self.scaler_y.transform(ytest_notnormalized)
        self.xtest          = xtest
        self.ytest          = ytest
        self.xtest_notnorm  = xtest_notnormalized
        self.ytest_notnorm  = ytest_notnormalized
        return
    
    #-----------------------------------------------------------------------------------
    # Training and computaton of prediction
    #-----------------------------------------------------------------------------------
    def training(self, verbose=False, epochs=EPOCHS, batch_size=BATCH_SIZE, 
                 learning_rate=LEARNING_RATE, validation_split=VALIDATION_SPLIT):
        """ Train the model with the options given in input
        """
        self.__check_attributes(['xtrain', 'ytrain', 'seed'])
        self.epochs           = epochs
        self.batch_size       = batch_size 
        self.learning_rate    = learning_rate
        self.validation_split = validation_split
        
        t0 = time.perf_counter()
        MyLPRegressor = MLPRegressor(hidden_layer_sizes  = self.hlayers_sizes,
            activation          = self.hidden_activation,
            solver              = 'adam', 
            max_iter            = epochs, # max_iter is the number of epochs for stochastic solvers (like adam)
            batch_size          = batch_size,
            alpha               = learning_rate,
            verbose             = verbose,
            random_state        = self.seed,
            validation_fraction = validation_split)

        model = MyLPRegressor.fit(self.xtrain, self.ytrain)

        self.training_time = time.perf_counter()-t0
        self.model = model
        return
        
    def compute_prediction(self, x, transform_output=False, transform_input=False, verbose=False):
        """ Prediction, can be used only after training
        If you want to remove the normalization, i.e. 
        to have the prediction in physical units, then use 
        transform_output=True (default is False, so that 
        NN.compute_prediction() is equivalent to model.prediction())
        If the input (i.e. x) is not already normalized, use
        transform_input = True
        """
        t0 = time.perf_counter()
        self.__check_attributes(['nfeatures', 'model'])
        x = np.array(x)
        if len(x.shape)==1:
            # if the input is given as a 1d-array...
            if len(x)==self.nfeatures:
                x = x.reshape((1,self.nfeatures)) # ...transform as row-vec
            else:
                raise ValueError('Wrong input-dimension')
        if transform_input:
            self.__check_attributes(['scaler_x'])
            x = self.scaler_x.transform(x)
        prediction = self.model.predict(x) 
        if transform_output:
            self.__check_attributes(['scaler_y'])
            out = self.scaler_y.inverse_transform(prediction)
        else:
            out = prediction
        
        pred_time = time.perf_counter()-t0
        if verbose:
            print('prediction-time: ', pred_time)
            
        return out
    
    #-----------------------------------------------------------------------------------
    # Utilities
    #-----------------------------------------------------------------------------------
    def print_info(self):
        attrs = dir(self)
        attr2skip = ['xtrain', 'ytrain', 'xtrain_notnorm', 'ytrain_notnorm', 
                     'xtest' , 'ytest' , 'xtest_notnorm' , 'ytest_notnorm'  ]
        for attr in attrs:
            value = getattr(self,attr)
            if (not '__' in attr) and (not type(value)==types.MethodType) and (not attr in attr2skip):
                print('{:20s}: {:}'.format(attr, value))
        return

    def compute_metrics_dict(self,x,y):
        """ Compute evaluation metrics 
        """
        def R2_numpy(y_true, y_pred):
            SS_res = np.sum((y_true - y_pred )**2)
            SS_tot = np.sum((y_true - np.mean(y_true))**2)
            return 1-SS_res/SS_tot
        self.__check_attributes(['nfeatures', 'model'])
        nfeatures   = self.nfeatures
        model       = self.model
        prediction  = self.compute_prediction(x)
        R2_vec      = np.zeros((nfeatures,))
        for i in range(0,nfeatures):
             R2_vec[i]        = R2_numpy(y[:,i], prediction[:,i])
        metrics_dict = {}
        metrics_dict['R2']          = R2_vec
        metrics_dict['R2mean']      = np.mean(R2_vec)
        return metrics_dict

    def print_metrics(self):
        """ Print (and eventually compute) evaluation metrics 
        """
        self.__check_attributes(['xtest', 'ytest'])
        metrics_dict = self.compute_metrics_dict(self.xtest,self.ytest)
        print('Final R2 mean  : {:.5f}'.format(metrics_dict['R2mean']))
        i = 0
        R2_vec = metrics_dict['R2']
        for R2 in metrics_dict['R2']:
            print('R2[{:2d}]         : {:.5f}'.format(i,R2))
            i+=1
        return
    
    #-----------------------------------------------------------------------------
    # Save and load (saved) model
    #-----------------------------------------------------------------------------
    def save_model(self, model_name=None, verbose=False, overwrite=True):
        """ Save weights of the model, scalers and fit options
        """
        attr2save = ['nfeatures', 'hlayers_sizes', 'batch_size', 'epochs', 'validation_split', \
                     'learning_rate', 'ntrain', 'seed', 'training_time']
        self.__check_attributes(['model', 'scaler_x', 'scaler_y']+attr2save)
        if model_name is None:
            model_name = 'model_nfeatures'+str(self.nfeatures)+'_'+datetime.today().strftime('%Y-%m-%d')
            if not overwrite:
                i = 1
                model_name_v0 = model_name
                while os.path.isdir(model_name):
                    model_name = model_name_v0 + '_v'+str(i)
                    i += 1
                if i>1:
                    print('+++ warning +++: ', model_name_v0, ' already exists and overwrite is False.\n',
                          'Renaming the new model as ', model_name, sep='')
        
        train_info = {}
        for a in attr2save:
            train_info[a] = getattr(self, a)
        scaler_x_dict = self.scaler_x.return_dict() 
        scaler_y_dict = self.scaler_y.return_dict() 
        
        if not os.path.isdir(model_name):
            os.mkdir(model_name)
        
        save_dill(model_name+'/scaler_x.dill'  , scaler_x_dict)
        save_dill(model_name+'/scaler_y.dill'  , scaler_y_dict)
        save_dill(model_name+'/train_info.dill', train_info)
        save_dill(model_name+'/model.dill', self.model)

        if verbose:
            print(model_name, 'saved')
        return
    
    def __load_model(self, model_name, verbose=False):
        """ Load things saved by self.save_model() and compile the model
        """
        if not os.path.isdir(model_name):
            raise ValueError(model_name+' not found!')
        scaler_x_dict = load_dill(model_name+'/scaler_x.dill')
        scaler_y_dict = load_dill(model_name+'/scaler_y.dill')
        train_info    = load_dill(model_name+'/train_info.dill')
        self.model    = load_dill(model_name+'/model.dill')
        Ax = scaler_x_dict['A']
        Bx = scaler_x_dict['B']
        std_scaler = scaler_x_dict['std_scaler']
        self.scaler_x = Scaler(Ax, Bx, std_scaler=std_scaler)
        Ay = scaler_y_dict['A']
        By = scaler_y_dict['B']
        std_scaler = scaler_y_dict['std_scaler']
        self.scaler_y = Scaler(Ay, By, std_scaler=std_scaler)
        train_info_keys = list(train_info.keys())
        for key in train_info_keys:
            setattr(self, key, train_info[key])
        if verbose:
            print(model_name, 'loaded')
        return
    
    #-----------------------------------------------------------------------------------
    # Function for plots
    #-----------------------------------------------------------------------------------
    def plot_predictions(self, x, show=True, save=False, figname='predictions.png'):
        """ Simple plot. For more 'elaborate' plots we rely
        on other modules (i.e. do not overcomplicate 
        this code with useless graphical functions)
        """
        self.__check_attributes(['nfeatures', 'ytest_notnorm'])
        nfeatures     = self.nfeatures
        ytest_notnorm = self.ytest_notnorm
        prediction    = self.compute_prediction(x, transform_output=True)
        if nfeatures<3:
            plot_cols = nfeatures
        else:
            plot_cols = 3
        rows = int(np.ceil(nfeatures/plot_cols))
        if rows>1:
            fig, axs = plt.subplots(rows, plot_cols, figsize = (25,17))
        else: 
            fig, axs = plt.subplots(rows, plot_cols, figsize = (22,9))
        feature = 0
        for i in range(0,rows):
            for j in range(0,plot_cols):
                if feature>=nfeatures:
                    break
                if rows>1:
                    ax = axs[i,j]
                else: 
                    ax = axs[j]
                ytest_notnorm_1d = ytest_notnorm[:,feature]
                prediction_1d    = prediction[:,feature]
                diff = np.abs(ytest_notnorm_1d-prediction_1d)
                ax.scatter(ytest_notnorm_1d, prediction_1d, s=2, c=diff, cmap='gist_rainbow')
                ax.plot(ytest_notnorm_1d, ytest_notnorm_1d, 'k')
                ax.set_ylabel('predicted - '+str(feature), fontsize=25)
                ax.set_xlabel('injected - '+str(feature), fontsize=25)
                feature+=1;
        if save:
            plt.savefig(figname,dpi=200,bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        return 
    
    def plot_err_histogram(self, feature_idx=0, color_rec=[0.7,0.7,0.7], color_pred=[0,1,0], nbins=31, 
                           logscale=False, name=None, abs_diff=False, fmin=None, fmax=None, verbose=False,
                           alpha_rec=1, alpha_pred=0.5, show=True, save=False, figname=None):
        """ Plot error-histogram for one feature. 
        The feature is chosen by feature_idx
        """
        self.__check_attributes(['ytest_notnorm', 'xtest_notnorm'])
        xtest_notnorm = self.xtest_notnorm
        ytest_notnorm = self.ytest_notnorm
        prediction = self.compute_prediction(xtest_notnorm, transform_output=True, transform_input=True)  
        inj  = ytest_notnorm[:,feature_idx]
        rec  = xtest_notnorm[:,feature_idx]
        pred =    prediction[:,feature_idx]
        if abs_diff:
            errors_rec  = (inj- rec)
            errors_pred = (inj-pred)
            xlab        = r'$\Delta y$'
            err_str     = 'difference'
        else:
            errors_rec  = (inj- rec)/inj
            errors_pred = (inj-pred)/inj
            xlab        = r'$\Delta y/y$'
            err_str     = ' rel diff '
        
        if fmin is None:
            min_rec  = min(errors_rec)
            min_pred = min(errors_pred)
            fmin     = min(min_rec, min_pred)
        if fmax is None:
            max_rec  = max(errors_rec)
            max_pred = max(errors_pred)
            fmax     = max(max_rec, max_pred)
        
        pred_min_outliers = 0
        pred_max_outliers = 0
        for i in range(len(errors_pred)):
            if errors_pred[i]<fmin:
                pred_min_outliers += 1
        for i in range(len(errors_pred)):
            if errors_pred[i]>fmax:
                pred_max_outliers += 1 
        rec_min_outliers = 0
        rec_max_outliers = 0
        for i in range(len(errors_rec)):
            if errors_rec[i]<fmin:
                rec_min_outliers += 1
        for i in range(len(errors_rec)):
            if errors_rec[i]>fmax:
                rec_max_outliers += 1 
        
        if verbose:
            print('mean rec  {:s} : {:9.5f} (std={:8.5f}, |{:s}|={:8.5f})'.format(err_str, 
                   np.mean(errors_rec),  np.std(errors_rec),  err_str, np.mean(np.abs(errors_rec))))
            print('mean pred {:s} : {:9.5f} (std={:8.5f}, |{:s}|={:8.5f})'.format(err_str, 
                   np.mean(errors_pred), np.std(errors_pred), err_str, np.mean(np.abs(errors_pred))))
            print('\n')
            print('median rec  {:s} : {:9.5f}'.format(err_str, np.median(errors_rec)))
            print('median pred {:s} : {:9.5f}'.format(err_str, np.median(errors_pred)))
            print('\n')
            print('recovery   below fmin={:6.2f}: {:d}'.format(fmin,  rec_min_outliers))
            print('recovery   above fmax={:6.2f}: {:d}'.format(fmax,  rec_max_outliers))
            print('prediction below fmin={:6.2f}: {:d}'.format(fmin, pred_min_outliers))
            print('prediction above fmax={:6.2f}: {:d}'.format(fmax, pred_max_outliers))

        fstep = (fmax-fmin)/nbins
        plt.figure
        plt.hist(errors_rec , bins=np.arange(fmin, fmax, fstep), alpha=alpha_rec,  color=color_rec, label='rec',
                 histtype='bar', ec='black')
        plt.hist(errors_pred, bins=np.arange(fmin, fmax, fstep), alpha=alpha_pred, color=color_pred, label='pred',
                 histtype='bar', ec='black')
        plt.legend(fontsize=20)
        plt.xlabel(xlab, fontsize=15)
        if logscale:
            plt.yscale('log')
        if name is not None:
            plt.title(name, fontsize=20)
        if save:
            if figname is None:
                figname = 'err_hist'+str(feature_idx)+'.png'
            plt.savefig(figname,dpi=200,bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        return

#######################################################################
# Cross-validator (on layers/architecture)
#######################################################################
class CrossValidator:
    """ Cross validation on architecture.
    Consider 1 and 2 layer(s) architectures and do a cross-val on the number of neurons
    for each layer. Compact-scaler is hard-coded+linear output 
    """
    def __init__(self,dict_name=None, neurons_max=300, neurons_step=50,
                 epochs=EPOCHS, batch_size=BATCH_SIZE, learning_rate=LEARNING_RATE, verbose=False,
                 xtrain=None, ytrain=None, xtest=None, ytest=None, seed=SEED, compact_bounds=None):
        nlayers_max        = 2 # hard-coded for now, but should be ok (i.e. no NN with >2 layers needed)
        self.nlayers_max   = nlayers_max
        self.neurons_max   = neurons_max
        self.neurons_step  = neurons_step
        self.epochs        = epochs
        self.batch_size    = batch_size
        self.learning_rate = learning_rate
        self.seed          = seed
        self.compact_bounds  = compact_bounds

        if xtrain is None or ytrain is None or xtest is None or ytest is None:
            raise ValueError('Incomplete data-input! Specifiy xtrain, ytrain, xtest, ytest')
        self.input_xtrain = xtrain
        self.input_ytrain = ytrain
        self.input_xtest  = xtest
        self.input_ytest  = ytest
        
        hlayers_sizes_list = []
        for i in range(neurons_step, neurons_max+1, neurons_step):
            for j in range(0, neurons_max+1, neurons_step):
                if j>0:
                    hlayers_size = (i,j)
                else:
                    hlayers_size = (i,)
                hlayers_sizes_list.append(hlayers_size)
        self.hlayers_sizes_list = hlayers_sizes_list
        
        if dict_name is None:
            dict_name = 'dict_nfeatures'+str(nfeatures)+'.dict'
        self.dict_name = dict_name
        cv_dict = load_dill(dict_name, verbose=verbose)
        self.cv_dict = cv_dict 
        return 

    def __param_to_key(self, hlayers_sizes):
        seed          = self.seed
        epochs        = self.epochs
        batch_size    = self.batch_size
        learning_rate = self.learning_rate
        nfeatures     = self.nfeatures
        compact_bounds  = self.compact_bounds
        
        key  = 'e:'+str(epochs)+'-bs:'+str(batch_size)+'-alpha:'+str(learning_rate)+'-'
        key += 'seed:'+str(self.seed)
        nlayers = len(hlayers_sizes)
        key += '-' + str(nlayers) + 'layers:'
        for i in range(0, nlayers):
            key += str(hlayers_sizes[i])
            if i<nlayers-1:
                key += '+'
        return key
    
    def __get_data(self, my_input, verbose=False):
        if type(my_input)==str:
            out = extract_data(my_input, verbose=verbose)
        else:
            out = my_input
        return out

    def crossval(self, verbose=False):
        """ Do cross-validation
        """
        seed               = self.seed
        epochs             = self.epochs
        batch_size         = self.batch_size
        learning_rate      = self.learning_rate
        hlayers_sizes_list = self.hlayers_sizes_list 
        compact_bounds     = self.compact_bounds
        xtrain_data = self.__get_data(self.input_xtrain, verbose=verbose)
        ytrain_data = self.__get_data(self.input_ytrain, verbose=verbose)
        xtest_data  = self.__get_data(self.input_xtest,  verbose=verbose)
        ytest_data  = self.__get_data(self.input_ytest,  verbose=verbose)
        self.nfeatures = len(xtrain_data[0,:])
        
        for hlayers_sizes in hlayers_sizes_list:
            key = self.__param_to_key(hlayers_sizes)
            if key in self.cv_dict:
                if verbose:
                    #print('{:90s} already saved in {:}'.format(key,self.dict_name))
                    print('key already present:',key)
            else:
                NN = RegressionNN(hlayers_sizes=hlayers_sizes, seed=seed)
                NN.load_train_dataset(xtrain_data=xtrain_data, ytrain_data=ytrain_data, 
                                      compact_bounds=compact_bounds)
                NN.training(epochs=epochs, batch_size=batch_size, learning_rate=learning_rate)
                NN.load_test_dataset(xtest_data=xtest_data, ytest_data=ytest_data)
                metrics_dict = NN.compute_metrics_dict(NN.xtest, NN.ytest)
                prediction   = NN.compute_prediction(NN.xtest_notnorm, transform_output=True, transform_input=True) 
               
                ttime        = NN.training_time
                del NN
                struct                 = lambda:0
                struct.metrics         = metrics_dict
                struct.hlayers_sizes   = hlayers_sizes
                struct.prediction      = prediction
                #struct.npars           = npars
                struct.nlayers         = len(hlayers_sizes)
                struct.epochs          = epochs
                struct.batch_size      = batch_size 
                struct.learning_rate   = self.learning_rate
                struct.seed            = seed
                struct.compact_bounds  = compact_bounds
                self.cv_dict[key] = struct 
                cv_dict           = self.cv_dict
                save_dill(self.dict_name, cv_dict)
                if verbose:
                    print('saving key: {:75s} ({:.3f} s)'.format(key, ttime))
        return

    #def plot(self, threshold=0.6, npars_lim=1e+7, feature_idx=-1, show=True, save=False, figname='crossval.png'):
    def plot(self, threshold=0.6, feature_idx=-1, show=True, save=False, figname='crossval.png'):
        """ Plots to check which NN-architecture produces the best results
        The metric used is R2. Use feature_idx=-1 to plot the mean of R2
        """
        if not hasattr(self, 'cv_dict'):
            raise ValueError('cross-val dict not defined! Call self.crossval() befor self.plot()')
        cv_dict   = self.cv_dict
        dict_keys = cv_dict.keys()
        i = 0
        max_neurons_l1 = 0
        max_neurons_l2 = 0
        max_score_l1   = 0
        max_score_l2   = 0
        max_score      = 0
        scores         = []
        #npars          = []
        hlayers        = []
        layer1_size    = []
        layer2_size    = []
        tot_neurons    = []
        for key in dict_keys:
            s = cv_dict[key]
            if feature_idx<0:
                score = s.metrics['R2mean']
                mytitle = 'mean of R2'
            else:
                score = s.metrics['R2'][feature_idx]
                mytitle = 'R2 of feature n.'+str(feature_idx)
            mytitle += ', threshold: '+str(threshold)
            
            if self.__param_to_key(s.hlayers_sizes)==key:
                scores.append(score)
                #npars.append(s.npars)
                hlayers.append(s.hlayers_sizes)
                neurons_l1 = s.hlayers_sizes[0]
                layer1_size.append(neurons_l1)
                tot_neurons_tmp = neurons_l1
                if s.nlayers>1:
                    neurons_l2 = s.hlayers_sizes[1]
                else:
                    neurons_l2 = 0
                layer2_size.append(neurons_l2)
                tot_neurons_tmp += neurons_l2
                tot_neurons.append(tot_neurons_tmp)
                if neurons_l1>max_neurons_l1:
                    max_neurons_l1 = neurons_l1
                if neurons_l2>max_neurons_l2:
                    max_neurons_l2 = neurons_l2
                if score>max_score:
                    max_score = score
                    max_score_l1 = neurons_l1
                    max_score_l2 = neurons_l2
                i += 1
        if i==0:
            print('no models found (or threshold too big)!')
            sys.exit()
        fig, axs = plt.subplots(1,2, figsize=(12, 4))
        sc=axs[0].scatter(layer1_size, layer2_size, c=scores, cmap='gist_rainbow')
        cbar = plt.colorbar(sc,ax=axs[0])
        cbar.set_label('score')
        axs[0].scatter(max_score_l1, max_score_l2, linewidth=2, s=150, facecolor='none', edgecolor=(0, 1, 0))
        axs[0].title.set_text(mytitle)
        axs[0].set_xlabel('n. neurons - layer 1')
        axs[0].set_ylabel('n. neurons - layer 2')
        axs[0].set_xlim(-5,max_neurons_l1+5)
        axs[0].set_ylim(-5,max_neurons_l2+5)
        #sc=axs[1].scatter(npars, scores, c=tot_neurons, cmap='viridis')
        sc=axs[1].scatter(tot_neurons, scores, c=tot_neurons, cmap='viridis')
        #cbar = plt.colorbar(sc,ax=axs[1])
        #cbar.set_label('total n. neurons')
        axs[1].title.set_text(mytitle)
        axs[1].set_xlabel('tot neurons')
        axs[1].set_ylabel('score')
        axs[1].set_ylim(threshold, min(np.max(scores)*1.005, 1)) 
        plt.subplots_adjust(wspace=0.4)
        if save:
            plt.savefig(figname,dpi=200,bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        return

#######################################################################
# Example
#######################################################################
if __name__ == '__main__':

    compact_bounds = {}
    compact_bounds['A'] = [0.5,0.5,0.1]
    compact_bounds['B'] = [3,3,3]
    
    loss_function = 'MSE' # 'MSE' or 'MQE'

    path = '/Users/simonealbanesi/repos/IPAM2021_ML/datasets/GSTLAL_EarlyWarning_Dataset/Dataset/m1m2Mc/'
    xtrain = path+'xtrain.csv'
    ytrain = path+'ytrain.csv'
    xtest  = path+'xtest.csv'
    ytest  = path+'ytest.csv'
     
    NN = RegressionNN(seed=None)
    NN.load_train_dataset(fname_xtrain=xtrain, fname_ytrain=ytrain, compact_bounds=compact_bounds)
    NN.training(verbose=True, epochs=10, validation_split=0.)
    NN.load_test_dataset(fname_xtest=xtest, fname_ytest=ytest) 
    NN.print_metrics()
    NN.plot_predictions(NN.xtest)

    dashes = '-'*80
    print(dashes, 'Save and load test:', dashes, sep='\n')
    NN.save_model(verbose=True, overwrite=True)
    NN2 = RegressionNN(model2load='model_nfeatures3_'+datetime.today().strftime('%Y-%m-%d'), verbose=True)
    NN2.load_test_dataset(fname_xtest=xtest, fname_ytest=ytest) 
    NN2.print_metrics() 
    print(dashes)
    NN.print_info()
    print(dashes)
    NN2.print_info()
    print(dashes)

    CV = CrossValidator(dict_name='test.dict', neurons_max=300, neurons_step=100, 
                        xtrain=xtrain, ytrain=ytrain, xtest=xtest, ytest=ytest, 
                        epochs=10, batch_size=128, seed=None, compact_bounds=compact_bounds)
    CV.crossval(verbose=True)
    CV.plot(feature_idx=-1, threshold=0.82)