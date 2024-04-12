# LiblibDownload
传闻说哩布哩布即将关闭免费下载模型，那就赶紧写个脚本来下载吧。
用得上的话右上角给点个星星:D

# 文件介绍

get_all_models_info.py

负责从哩布的接口获取所有指定类别的模型信息，比如100033代表“建筑与空间设计”类别。获取的信息包括Checkpoint模型和LoRA模型，底座模型包括SD1.5和SDXL。
代码将在当前目录下生成一个json文件，里面包含所有的模型必要信息，包括每个模型每个版本的下载链接和图片链接等。

download.py

负责根据get_all_models_info.py生成的json文件执行下载。下载过程如下：
1. 建立Checkpoint和LoRA两个目录
2. 根据模型类型和模型名称建立相应的子目录
3. 根据模型版本的名称建立相应的子目录
4. 根据模型地址和封面图片地址下载到相应的子目录中
5. 下载地址的文件名经常是无意义的，按照模型版本名称重命名

aria2c.exe

一个开源的下载程序，download.py会调用它下载那些巨大的文件，要放到跟download.py同一个目录里。
有条件的最好自己去github下载这个软件并解压放到同一个目录里，地址：
https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-32bit-build1.zip


# 用法

1. 没有python的话先安装python。
2. 下载代码，存到某个目录里并进入目录。
3. 用编辑器打开get_all_models_info.py，在代码最头上有model_category = 100033字样，这是默认的下载“建筑与空间设计”类别。如果需要下载别的类别请自行替换相应的category代码。
4. 命令行运行python get_all_models_info.py，静等大概十几分钟，会获得一个all_models_100033.json这样的json文件。命令行上会有一些输出，不会太无聊的。其实哩布也不是每天增加一堆模型，所以你只要建筑类的模型的话，可以跳过这一步，直接用all_models_100033.json就行
5. 命令行运行python download.py，会自动根据上面的json文件来下载。


# 备注

1. 根据群友要求加入了“下载量小于100的不要下载”和“发布时间没超过一个月的不要下载”功能‘
2. 如果需要查询不是“建筑与空间设计”的其他类别，请在运行get_all_models_info.py之前修改文件头部的“tagsV2Id=”部分，修改成什么值可以参见“查询用的参数见这里.json”
