import numpy as np
import cv2
import os
from tqdm import tqdm
from natsort import natsorted
import re
import torch
from Model import UNet, UNet_attention
import torch.nn.functional as F
import matplotlib.pyplot as plt
from skimage.measure import label
from scipy.spatial.distance import directed_hausdorff
import pandas as pd
from TransUnet.vit_seg_modeling import VisionTransformer as ViT_seg
from TransUnet.vit_seg_modeling import CONFIGS as CONFIGS_ViT_seg
from torchvision import transforms
from scipy import ndimage
from scipy.ndimage.interpolation import zoom
import torchvision.transforms.functional as TF


image_ext = ['.jpg', '.jpeg', '.webp', '.bmp', '.png', '.tif', '.PNG', '.tiff']


def NoiseFiltering(img, thresh=150):
    unique_labels = np.unique(img)
    for i in unique_labels:
        if i == 0:
            continue

        binary_img = np.zeros_like(img)
        binary_img[img == i] = 1
        label_img = label(binary_img)
        label_list = list(np.unique(label_img))
        for lbl in label_list:
            if (label_img == lbl).sum() < thresh:
                img[label_img == lbl] = 0
    return img


def natural_sort(l):
    def convert(text): return int(text) if text.isdigit() else text.lower()
    def alphanum_key(key): return [convert(c)
                                   for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)

"""
def get_image_list(self, path):  #from dataloader for numbers are
        image_paths = []
        for current_path in path:
            for maindir, subdir, file_name_list in os.walk(current_path):
                for filename in file_name_list:
                    #if 'gold' in filename:
                        #continue
                    apath = os.path.join(maindir, filename)
                    ext = os.path.splitext(apath)[1]
                    if ext in image_ext:
                        image_paths.append(apath)
        return self.natural_sort(image_paths)   #installed but not tried"""
def get_image_list(path):   #original
    image_names = []
    for maindir, subdir, file_name_list in os.walk(path):
        for filename in file_name_list:
            #if 'gold' not in filename:
            apath = os.path.join(maindir, filename)
            ext = os.path.splitext(apath)[1]
            if ext in image_ext:
                image_names.append(apath)
    return natsorted(image_names)


"""def get_image_list(path):   #original
    image_names = []
    for maindir, subdir, file_name_list in os.walk(path):
        for filename in file_name_list:
            if 'gold' not in filename:
                apath = os.path.join(maindir, filename)
                ext = os.path.splitext(apath)[1]
                if ext in image_ext:
                    image_names.append(apath)
    return natsorted(image_names)"""


patch_size = 16
num_of_class=9
img_size = (128,1024)
use_cuda = True
model_path = '/kuacc/users/dozkan23/hpc_run/TransUnet/trans_retinallayers/models/epoch29.pt'
config_vit = CONFIGS_ViT_seg["ViT-B_16"]
config_vit.n_classes = 9
config_vit.n_skip = 0
config_vit.patches.size = (patch_size, patch_size)
config_vit.patches.grid = None
device = "cuda:0"
dtype = torch.cuda.FloatTensor
model = ViT_seg(config_vit, img_size=img_size[0], num_classes=9).cuda()
model.load_state_dict(torch.load(model_path))
model.eval()

# model = UNet(1, 4, 64,
#              use_cuda, False, 0.2)
# model = UNet_attention(1, 4, 64,
#                 use_cuda, False, 0.2)

#model.load_state_dict(torch.load(model_path))
#model.eval()
#device = "cuda:0"
#dtype = torch.cuda.FloatTensor
model.to(device=device)


save_dir = 'transunet_eye'
test_path = '/userfiles/cgunduz/datasets/retinal_layers/test'
image_list = get_image_list(test_path)

label_colors = label_colors = [
    (0, 0, 0),       # Background
    (255, 0, 0),     # Layer 1
    (0, 255, 0),     # Layer 2
    (0, 0, 255),     # Layer 3
    (255, 255, 0),   # Layer 4
    (0, 255, 255),   # Layer 5
    (255, 0, 255),   # Layer 6
    (192, 192, 192), # Layer 7
    (128, 128, 128)  # Layer 8
]


def create_rgb_mask(mask, label_colors):
    rgb_mask = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8) #i changed here 
    
    rgb_mask[mask == 1] = label_colors[0]
    rgb_mask[mask == 2] = label_colors[1]
    rgb_mask[mask == 3] = label_colors[2]
    rgb_mask[mask == 4] = label_colors[3]
    rgb_mask[mask == 5] = label_colors[4]
    rgb_mask[mask == 6] = label_colors[5]
    rgb_mask[mask == 7] = label_colors[6]
    rgb_mask[mask == 8] = label_colors[7]
    rgb_mask[mask == 9] = label_colors[8]
    return rgb_mask


if not os.path.exists(save_dir):
    os.mkdir(save_dir)


class_names = {0: 'background', 1: 'red', 2: 'green', 3: 'blue'}

# red = 1;
# green = 2;
# yellow = 4;
# blue = 3;



def preprocess(img_org):
    imgHeight, imgWidth = img_org.shape[0], img_org.shape[1]
    if imgHeight != img_size[0] or imgWidth != img_size[1]:
        img_input = zoom(img_org, (img_size[1] / imgWidth,img_size[0] / imgHeight), order=3) # i changed the order instead of img_size[1] / imgWidth,img_size[0] / imgHeight) 
        print('XXXX')
    else:
        img_input = img_org
    #z normalizization
    mean3d = np.mean(img_input, axis=(0,1))
    std3d = np.std(img_input, axis=(0,1))
    img_input = (img_input-mean3d)/std3d
    
    img_input = torch.from_numpy(img_input).unsqueeze(0).unsqueeze(0).float().cuda()
    
    # # Transform to tensor
    # img_input = TF.to_tensor(img_input)
    # # Normalize
    # img_input = TF.normalize(img_input,[0.5], [0.5]).unsqueeze(0).cuda()

    return img_input

class Results_mc:
    def __init__(self, save_dir,num_of_class, tolerance=0):
        self.save_dir = save_dir
        self.tolerance = tolerance
        self.num_of_class = num_of_class
        self.class_result_dict = {}
        for i in range(self.num_of_class):
            self.class_result_dict[i] = {'precision': [], 'recall': [
            ], 'f1': [], 'dice_score': [], 'iou_score': [], "hausdorff_distance": []}

    def compare(self, y_true, y_pred):
        """
        calculate metrics threating each pixel as a sample
        """
        smoothening_factor = 1e-6
        for i in range(self.num_of_class):
            intersection = np.sum((y_pred == i) * (y_true == i))
            if (i not in y_true and i not in y_pred):
                self.class_result_dict[i]['iou_score'].append(1)
                self.class_result_dict[i]['dice_score'].append(1)
                self.class_result_dict[i]['precision'].append(1)
                self.class_result_dict[i]['recall'].append(1)
                self.class_result_dict[i]['f1'].append(1)
                self.class_result_dict[i]['hausdorff_distance'].append(0)
                continue
            y_true_area = np.sum((y_true == i))
            y_pred_area = np.sum((y_pred == i))
            combined_area = y_true_area + y_pred_area
            iou = (intersection + smoothening_factor) / \
                (combined_area - intersection + smoothening_factor)
            self.class_result_dict[i]['iou_score'].append(iou)

            dice_score = 2 * ((intersection + smoothening_factor) /
                              (combined_area + smoothening_factor))
            self.class_result_dict[i]['dice_score'].append(dice_score)

            # true positives
            tp_pp = np.sum((y_pred == i) & (y_true == i))
            # true negatives
            tn_pp = np.sum((y_pred == 0) & (y_true == 0))
            # false positives
            fp_pp = np.sum((y_pred == i) & (y_true != i))
            # false negatives
            fn_pp = np.sum((y_pred != i) & (y_true == i))

            precision = tp_pp / (tp_pp + fp_pp + smoothening_factor)
            recall = tp_pp / (tp_pp + fn_pp + smoothening_factor)
            f1_score = 2 * tp_pp / (2 * tp_pp + fp_pp + fn_pp)
            self.class_result_dict[i]['precision'].append(precision)
            self.class_result_dict[i]['recall'].append(recall)
            self.class_result_dict[i]['f1'].append(f1_score)

            y_binary_class_gt = np.zeros_like(y_true)
            y_binary_class_gt[y_true == i] = 1
            y_binary_class_pred = np.zeros_like(y_pred)
            y_binary_class_pred[y_pred == i] = 1
            if not np.all(y_binary_class_gt == 0) or np.all(y_binary_class_pred == 1):
                hausdorff = max(directed_hausdorff(y_binary_class_gt, y_binary_class_pred)[
                    0], directed_hausdorff(y_binary_class_pred, y_binary_class_gt)[0])
            self.class_result_dict[i]['hausdorff_distance'].append(hausdorff)

    def calculate_metrics(self):
        f = open(os.path.join(self.save_dir, 'result.txt'), 'w')

        f.write('Image-wise analysis:\n')

        for i in range(self.num_of_class):
            class_name = class_names[i]
            df = pd.DataFrame.from_dict(self.class_result_dict[i])
            df.to_csv(os.path.join(self.save_dir,
                      '{}.csv'.format(class_name)), index=False)
            f.write('{} \n'.format(class_name))
            precision = round(sum(
                self.class_result_dict[i]['precision'])/len(self.class_result_dict[i]['precision']), 3)
            recall = round(sum(
                self.class_result_dict[i]['recall'])/len(self.class_result_dict[i]['recall']), 3)
            f1_score = round(
                sum(self.class_result_dict[i]['f1'])/len(self.class_result_dict[i]['f1']), 3)
            dice_score = round(sum(
                self.class_result_dict[i]['dice_score'])/len(self.class_result_dict[i]['dice_score']), 3)
            iou_based_image = round(sum(
                self.class_result_dict[i]['iou_score'])/len(self.class_result_dict[i]['iou_score']), 3)
            hd_image = round(sum(
                self.class_result_dict[i]['hausdorff_distance'])/len(self.class_result_dict[i]['hausdorff_distance']), 3)

            f.write('precision: {}\n'.format(precision))
            f.write('recall: {}\n'.format(recall))
            f.write('f1: {}\n'.format(f1_score))
            f.write("Dice Score:"+str(dice_score)+'\n')
            f.write("IOU Score:" + str(iou_based_image)+'\n')
            f.write("Hausdorff Score:" + str(hd_image)+'\n')
            f.write("\n")
        f.close()


results = Results_mc(save_dir, num_of_class)

for img_path in tqdm(image_list):
    image_name = img_path.split('/')[-1]
    image_name = image_name[:image_name.rfind('.')]
    img_org = cv2.imread(img_path, 0)

    img_input = preprocess(img_org)
    imgHeight, imgWidth = img_org.shape[0], img_org.shape[1]

    model.eval()
    with torch.no_grad():
        outputs = model(img_input)
        print(outputs.shape, "outputs")
        out=outputs.squeeze(0).squeeze(0)
        print(out.shape, "after  1 squeze out shape")
        probs = F.softmax(outputs, dim=1)  # Apply softmax along the class dimension
        out = torch.argmax(probs, dim=1).squeeze(0)  #why dim 1
        print(out.shape, "after all")
        #out=outputs.squeeze(0).squeeze(0)
        #probs = F.sigmoid(out)  #burdaki tüm resim icin degil de her classı kendi içinde mi sigmoidden geçiriyor.
        #out = (probs >= 0.5)
        #out = torch.argmax(probs, dim=1).squeeze(0)  #i chnaged here for softmax
        out = out.cpu().detach().numpy()
        if imgHeight != img_size[0] or imgWidth != img_size[1]:
            pred = zoom(out, (imgHeight / img_size[0], imgWidth / img_size[1]), order=0)
            print(pred.shape)
        else:
            pred = out
            print(pred.shape, "else girdi, pred shape")

    probs = probs.data.cpu().numpy()

    # read gt mask
    mask_path =  img_path[:img_path.rfind('.')] + '.png'
    mask_path=mask_path.replace('test','golds')
    mask = cv2.imread(mask_path, 0)
    print(mask.shape, "before function, gt mask shape")
    # create rgb masks
    rgb_mask = create_rgb_mask(mask, label_colors)
    print(rgb_mask.shape, "after mask function gt rgb mask shape")

    # score1 = probs[0, 1, :, :] * 255
    # score2 = probs[0, 2, :, :] * 255
    # score3 = probs[0, 3, :, :] * 255

    # score1_img = score1.astype(np.uint8)
    # score2_img = score2.astype(np.uint8)
    # score3_img = score3.astype(np.uint8)
    rgb_mask_pred = create_rgb_mask(pred, label_colors)
    print(rgb_mask.shape, "after mask function pred rgb mask shape")

    results.compare(mask, pred)

    # fig, axs = plt.subplots(1, 3)
    # fig.set_figheight(8)
    # fig.set_figwidth(16)
    # axs[0].imshow(score1_img, cmap='gray')
    # axs[0].title.set_text('class 1 (red)')
    # axs[1].imshow(score2_img, cmap='gray')
    # axs[1].title.set_text('class 2 (green)')
    # axs[2].imshow(score3_img, cmap='gray')
    # axs[2].title.set_text('class 3 (yellow)')
    # axs[1, 1].imshow(score4_img, cmap='gray')
    # axs[1, 1].title.set_text('class 4 (yellow)')
    # fig.savefig(os.path.join(save_dir, image_name+'_probdist.png'))
    # fig.clf()
    # plt.close(fig)

    seperater = np.zeros([img_org.shape[0], 15, 3], dtype=np.uint8)
    seperater.fill(155)

    # save_img_dist = np.hstack(
    #     [img_org, seperater, mask_dist, seperater, pred_dist])
    # cv2.imwrite(os.path.join(results_save_dir_images,
    #             image_name+'_dist.png'), save_img_dist)

    rgb_mask = cv2.cvtColor(rgb_mask, cv2.COLOR_BGR2RGB)
    rgb_mask_pred = cv2.cvtColor(rgb_mask_pred, cv2.COLOR_BGR2RGB)

    save_img_bin = np.hstack(
        [cv2.cvtColor(img_org, cv2.COLOR_GRAY2RGB), seperater, rgb_mask, seperater, rgb_mask_pred])
    cv2.imwrite(os.path.join(save_dir, image_name+'.png'), save_img_bin)


results.calculate_metrics()
